import unittest
from unittest.mock import MagicMock, patch
import json
import uuid
import base64
from appsync_ws_client.client import GraphQLWebSocketClient  # Adjust import as necessary
from appsync_ws_client.exceptions import MaxRetriesExceeded


class TestGraphQLWebSocketClient(unittest.TestCase):
    """Unit tests for GraphQLWebSocketClient"""

    def setUp(self):
        """Set up mock WebSocketApp and initialize client for each test."""
        self.url = "wss://example.com/graphql"
        self.auth_function = MagicMock(return_value={"host": "xx.appsync-api.region.amazonaws.com", "Authorization": "Bearer token"})
        self.client = GraphQLWebSocketClient(url=self.url, auth_function=self.auth_function)

    def test_initialization(self):
        """Test client initialization and default values."""
        self.assertEqual(self.client.url, self.url)
        self.assertEqual(self.client.auth_function, self.auth_function)
        self.assertFalse(self.client._is_open)
        self.assertEqual(self.client.max_retries, 5)

    def test_build_ws_url(self):
        """Test WebSocket URL building with encoded headers."""
        url = self.client._build_ws_url()
        auth_info = self.auth_function()
        headers_encoded = base64.b64encode(json.dumps(auth_info).encode()).decode()
        expected_url = f"{self.url}?header={headers_encoded}&payload={base64.b64encode(json.dumps({}).encode()).decode()}"
        self.assertEqual(url, expected_url)

    # Connection-related tests
    @patch('threading.Thread.start')
    @patch('appsync_ws_client.client.websocket.WebSocketApp')
    def test_connect(self, MockWebSocketApp, mock_thread_start):
        """Test the connect method initializes the WebSocket connection."""
        self.client.connect()
        MockWebSocketApp.assert_called_with(
            self.client._build_ws_url(),
            subprotocols=["graphql-ws"],
            on_open=self.client._on_open,
            on_message=self.client._on_message,
            on_error=self.client._on_error,
            on_close=self.client._on_close,
        )
        mock_thread_start.assert_called_once()

    @patch('appsync_ws_client.client.websocket.WebSocketApp')
    @patch('appsync_ws_client.client.logger')
    def test_connect_failure(self, mock_logger, MockWebSocketApp):
        """Test handling connection failure and ensuring reconnection is attempted."""
        # Configure the mock to raise an exception when connecting
        MockWebSocketApp.side_effect = Exception("Connection failed")
        with patch('appsync_ws_client.client.GraphQLWebSocketClient._attempt_reconnect') as mock_attempt_reconnect:
            self.client.connect()
            mock_logger.error.assert_called_once_with("Failed to connect: Connection failed")
            mock_attempt_reconnect.assert_called_once()

    def test_on_open(self):
        """Test the _on_open handler sets the connection state and sends init message."""
        self.client._send_message = MagicMock()
        self.client._on_open(None)
        self.assertTrue(self.client._is_open)
        self.client._send_message.assert_called_once_with({"type": "connection_init"})

    def test_on_close(self):
        """Test the _on_close handler resets the connection state."""
        with patch('appsync_ws_client.client.GraphQLWebSocketClient._attempt_reconnect') as mock_attempt_reconnect:
            self.client._on_close(None, 1000, "Closed")
            self.assertFalse(self.client._is_open)
            mock_attempt_reconnect.assert_called_once()

    # Reconnection-related tests
    @patch("time.sleep", return_value=None)
    def test_attempt_reconnect_within_max_retries(self, mock_sleep):
        """Test reconnection attempts within max retries."""
        self.client.retry_count = 0
        self.client.connect = MagicMock()
        self.client._attempt_reconnect()
        self.client.connect.assert_called_once()
        self.assertEqual(self.client.retry_count, 1)

    @patch("time.sleep", return_value=None)
    def test_attempt_reconnect_exceeds_max_retries(self, mock_sleep):
        """Test reconnection attempt exceeding max retries."""
        self.client.retry_count = self.client.max_retries
        with self.assertRaises(MaxRetriesExceeded):
            self.client._attempt_reconnect()

    # Message handling tests
    def test_on_message_connection_ack(self):
        """Test connection acknowledgment (connection_ack) message handling."""
        self.client._acknowledged_event = MagicMock()
        self.client._on_message(None, json.dumps({"type": "connection_ack"}))
        self.client._acknowledged_event.set.assert_called_once()

    @patch('appsync_ws_client.client.logger')
    def test_on_message_keep_alive(self, mock_logger):
        """Test handling of keep-alive (ka) messages."""
        self.client._on_message(None, json.dumps({"type": "ka"}))
        mock_logger.debug.assert_called_once_with("Keep-alive received.")

    def test_on_message_data(self):
        """Test handling data messages and invoking the correct callback."""
        callback = MagicMock()
        subscription_id = str(uuid.uuid4())
        self.client.subscriptions[subscription_id] = {"callback": callback}
        message = json.dumps({"type": "data", "id": subscription_id, "payload": {"data": "test"}})
        self.client._on_message(None, message)
        callback.assert_called_once_with({"data": "test"})

    @patch('appsync_ws_client.client.logger')
    def test_on_message_error(self, mock_logger):
        """Test handling error messages."""
        self.client._on_message(None, json.dumps({"type": "error", "payload": "test_error"}))
        mock_logger.error.assert_called_once_with("Error received: test_error")

    @patch('appsync_ws_client.client.GraphQLWebSocketClient._attempt_reconnect')
    def test_on_error(self, mock_attempt_reconnect):
        """Test the _on_error handler triggers a reconnection attempt."""
        self.client._on_error(None, Exception("test_error"))
        mock_attempt_reconnect.assert_called_once()

    # Subscription-related tests
    @patch("uuid.uuid4", return_value="test-subscription-id")
    @patch('appsync_ws_client.client.GraphQLWebSocketClient._send_message')
    def test_subscribe(self, mock_send_message, mock_uuid):
        """Test subscribing to a GraphQL query."""
        query = "subscription { test }"
        variables = {"key": "value"}
        callback = MagicMock()

        self.client._acknowledged_event.set()
        subscription_id = self.client.subscribe(query, variables, callback)
        expected_message = {
            "id": "test-subscription-id",
            "type": "start",
            "payload": {
                "data": json.dumps({"query": query, "variables": variables}),
                "extensions": {"authorization": self.auth_function()},
            },
        }
        mock_send_message.assert_called_once_with(expected_message)
        self.assertEqual(subscription_id, "test-subscription-id")

    @patch('appsync_ws_client.client.logger')
    def test_subscribe_acknowledged_timeout(self, mock_logger):
        """Test subscribing without connection acknowledgment."""
        self.client._acknowledged_event = MagicMock()
        self.client._acknowledged_event.wait.return_value = False
        with self.assertRaises(TimeoutError):
            self.client.subscribe("subscription { test }", {}, MagicMock())
            mock_logger.error.assert_called_once_with("Connection acknowledgment timeout.")

    @patch('appsync_ws_client.client.GraphQLWebSocketClient._send_message')
    def test_unsubscribe(self, mock_send_message):
        """Test unsubscribing from a subscription."""
        subscription_id = "test-subscription-id"
        self.client.subscriptions[subscription_id] = {"callback": MagicMock()}
        self.client.unsubscribe(subscription_id)
        mock_send_message.assert_called_once_with({"id": subscription_id, "type": "stop"})
        self.assertNotIn(subscription_id, self.client.subscriptions)

    # WebSocket send tests
    def test_send_message_when_open(self):
        """Test sending a message when the WebSocket connection is open."""
        self.client._is_open = True
        self.client.ws = MagicMock()
        message = {"type": "test"}
        self.client._send_message(message)
        self.client.ws.send.assert_called_once_with(json.dumps(message))

    @patch('appsync_ws_client.client.logger')
    def test_send_message_when_closed(self, mock_logger):
        """Test sending a message when the WebSocket connection is closed."""
        self.client._is_open = False
        message = {"type": "test"}
        self.client._send_message(message)
        mock_logger.warning.assert_called_once_with("WebSocket is not open. Cannot send message.")

    # Utility function tests
    def test_is_connection_open(self):
        """Test checking if the WebSocket connection is open."""
        self.client._is_open = True
        self.assertTrue(self.client.isConnectionOpen())
        self.client._is_open = False
        self.assertFalse(self.client.isConnectionOpen())

    def test_is_acknowledged(self):
        """Test checking if the connection is acknowledged."""
        self.client._acknowledged_event.set()
        self.assertTrue(self.client.isAcknowledged())
        self.client._acknowledged_event.clear()
        self.assertFalse(self.client.isAcknowledged())

    # Cleanup tests
    def test_close(self):
        """Test the close method to ensure WebSocket is closed and connection state reset."""
        self.client.ws = MagicMock()
        self.client._is_open = True
        self.client.close()
        self.client.ws.close.assert_called_once()
        self.assertFalse(self.client._is_open)

    @patch('appsync_ws_client.client.GraphQLWebSocketClient.close')
    def test_del(self, mock_close):
        """Test the deletion of the client triggers the close method."""
        del self.client
        mock_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
