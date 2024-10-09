import time
import websocket
import json
import base64
import threading
import uuid
import logging
from typing import Callable, Dict, Any
from .exceptions import MaxRetriesExceeded

logger = logging.getLogger(__name__)


class GraphQLWebSocketClient:
    def __init__(self, url: str, auth_function: Callable[[], Dict[str, str]], max_retries: int = 5):
        self.url = url
        self.auth_function = auth_function
        self.ws = None
        self.subscriptions = {}
        self._is_open = False
        self._acknowledged_event = threading.Event()
        self.max_retries = max_retries
        self.retry_count = 0
        self.lock = threading.Lock()

    def _build_ws_url(self) -> str:
        """
        Build the WebSocket URL with authentication headers.
        """
        auth_info = self.auth_function()
        headers_encoded = base64.b64encode(json.dumps(auth_info).encode()).decode()
        all_url = f"{self.url}?header={headers_encoded}&payload={base64.b64encode(json.dumps({}).encode()).decode()}"
        logger.debug(f"WebSocket URL: {all_url}")
        return all_url

    def connect(self):
        """
        Establish the WebSocket connection.
        """
        try:
            ws_url = self._build_ws_url()
            self.ws = websocket.WebSocketApp(
                ws_url,
                subprotocols=["graphql-ws"],
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            thread = threading.Thread(target=self.ws.run_forever)
            thread.daemon = True
            thread.start()
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._attempt_reconnect()

    def _on_open(self, ws):
        """
        WebSocket open event handler. Sends connection initialization message.
        """
        self._is_open = True
        self._acknowledged_event.clear()
        self._send_message({"type": "connection_init"})
        logger.info("WebSocket connection opened.")
        self.retry_count = 0

    def _on_message(self, ws, message):
        """
        WebSocket message event handler. Process incoming messages.
        """
        msg = json.loads(message)
        message_type = msg.get('type')

        if message_type == "connection_ack":
            self._acknowledged_event.set()
            logger.info("Connection acknowledged.")
        elif message_type == "ka":
            logger.debug("Keep-alive received.")
        elif message_type == "data":
            subscription_id = msg.get('id')
            if subscription_id and subscription_id in self.subscriptions:
                callback = self.subscriptions[subscription_id]['callback']
                callback(msg['payload'])
        elif message_type == "error":
            logger.error(f"Error received: {msg.get('payload')}")

    def _on_error(self, ws, error):
        """
        WebSocket error event handler.
        """
        logger.error(f"WebSocket error occurred: {error}")
        if isinstance(error, Exception):
            logger.exception("Exception details:", exc_info=error)
        self._attempt_reconnect()

    def _on_close(self, ws, close_status_code, close_msg):
        """
        WebSocket close event handler.
        """
        self._is_open = False
        self._acknowledged_event.clear()
        logger.warning(f"WebSocket closed: {close_status_code}, message: {close_msg}")
        self._attempt_reconnect()

    def _attempt_reconnect(self):
        """
        Attempt to reconnect to the WebSocket.
        """
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            wait_time = 2**self.retry_count + (0.5 * self.retry_count)
            logger.info(f"Reconnecting in {wait_time} seconds...")
            time.sleep(wait_time)
            self.connect()
        else:
            raise MaxRetriesExceeded("Max retries reached.")

    def subscribe(
        self, query: str, variables: Dict[str, Any], callback: Callable[[Dict[str, Any]], None], acknowledgment_timeout: int = 10
    ) -> str:
        """
        Subscribe to a GraphQL query via WebSocket.

        :param query: GraphQL query as a string.
        :param variables: Variables for the GraphQL query.
        :param callback: A callback function that handles the incoming data.
        :return: The subscription ID (used for unsubscribing later).
        """
        # Wait for connection to be acknowledged before subscribing
        if not self._acknowledged_event.wait(timeout=acknowledgment_timeout):
            logger.error("Connection acknowledgment timeout.")
            raise TimeoutError("Connection acknowledgment timeout.")

        subscription_id = str(uuid.uuid4())
        self.subscriptions[subscription_id] = {'query': query, 'variables': variables, 'callback': callback}

        message = {
            "id": subscription_id,
            "type": "start",
            "payload": {
                "data": json.dumps({"query": query, "variables": variables}),
                "extensions": {"authorization": self.auth_function()},
            },
        }
        self._send_message(message)
        logger.info(f"Subscribed with ID: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str):
        """
        Unsubscribe from a subscription.
        :param subscription_id: The subscription ID.
        """
        with self.lock:
            if subscription_id in self.subscriptions:
                self._send_message({"id": subscription_id, "type": "stop"})
                del self.subscriptions[subscription_id]
                logger.info(f"Unsubscribed from: {subscription_id}")

    def _send_message(self, message: Dict[str, Any]):
        """
        Send a message over the WebSocket.
        """
        with self.lock:
            if self.ws and self._is_open:
                self.ws.send(json.dumps(message))
            else:
                logger.warning("WebSocket is not open. Cannot send message.")

    def isConnectionOpen(self):
        """
        Check if the WebSocket connection is open.
        """
        return self._is_open

    def isAcknowledged(self):
        """
        Check if the connection has been acknowledged.
        """
        return self._acknowledged_event.is_set()

    def close(self):
        """
        Close the WebSocket connection.
        """
        with self.lock:
            if self.ws:
                self.ws.close()
                self._is_open = False
                logger.info("WebSocket connection closed.")

    def __del__(self):
        self.close()
