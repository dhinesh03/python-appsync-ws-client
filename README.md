
# AWS AppSync WebSocket Client

A Python client for subscribing to AWS AppSync GraphQL APIs via WebSockets. This package allows you to connect to the AWS AppSync WebSocket API, handle GraphQL subscriptions, and manage reconnections and retries seamlessly.

## Features

- **GraphQL Subscriptions**: Easily subscribe to GraphQL queries over WebSockets.
- **Automatic Reconnection**: Handles reconnection attempts in case of dropped WebSocket connections.
- **Thread-safe**: Manages multiple subscriptions with thread-safe operations.
- **Callback Handling**: Provides a way to specify callback functions that process subscription data.

## Installation

Install the package via pip:

```bash
pip install appsync-ws-client
```

## Usage

### 1. Initialize the Client

To use the client, provide the WebSocket URL and an authentication function that returns the necessary headers.

```python
from appsync_ws_client.client import GraphQLWebSocketClient

def get_auth_headers():
    return {
        "host": "xxx.appsync-api.<region>.amazonaws.com",
        "Authorization": "<ACCESS_TOKEN>",
    }

url = "wss://<your-appsync-endpoint>"
client = GraphQLWebSocketClient(url, auth_function=get_auth_headers)
client.connect()
```

### 2. Subscribing to a GraphQL Query

You can subscribe to a GraphQL query using the `subscribe` method. The subscription requires a GraphQL query, variables (if any), and a callback function to handle the subscription data.

```python
query = '''
subscription OnPriceUpdate {
    onPriceUpdate {
        id
        price
        timestamp
    }
}
'''

def handle_subscription_data(data):
    print("Received subscription data:", data)

subscription_id = client.subscribe(query, variables={}, callback=handle_subscription_data)
```

### 3. Unsubscribing

To unsubscribe from a subscription, use the `unsubscribe` method with the `subscription_id` that was returned when you subscribed.

```python
client.unsubscribe(subscription_id)
```

### 4. Closing the Connection

Ensure you close the WebSocket connection properly when done:

```python
client.close()
```

### 5. Handling Reconnection

The client automatically attempts to reconnect when a WebSocket connection drops. You can control the number of retry attempts by passing `max_retries` to the client. For example:

```python
client = GraphQLWebSocketClient(url, auth_function=get_auth_headers, max_retries=10)
client.connect()
```

## Error Handling

The package will raise the following errors:

- **`TimeoutError`**: Raised when the connection acknowledgment times out.
- **`MaxRetriesExceeded`**: Raised when the maximum number of reconnection attempts is exceeded.

You can also handle WebSocket errors using the client’s internal logging.

## Logging

Logging is built in to help monitor the WebSocket connection and subscription process. Make sure to configure logging in your application as necessary:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

## Example

Here is a full example of setting up the client and subscribing to a GraphQL subscription:

```python
import time
import logging
from appsync_ws_client.client import GraphQLWebSocketClient

logging.basicConfig(level=logging.INFO)

def get_auth_headers():
    return {
        "host": "xxx.appsync-api.<region>.amazonaws.com",
        "Authorization": "<ACCESS_TOKEN>",
    }

url = "wss://<your-appsync-endpoint>"
client = GraphQLWebSocketClient(url, auth_function=get_auth_headers)
client.connect()

query = '''
subscription OnPriceUpdate {
    onPriceUpdate {
        id
        price
        timestamp
    }
}
'''

def handle_subscription_data(data):
    print("Received subscription data:", data)

subscription_id = client.subscribe(query, variables={}, callback=handle_subscription_data)

try:
    while True:
        time.sleep(1)  # Keeps the main program alive
except KeyboardInterrupt:
    print("Closing WebSocket and shutting down...")
    client.close()


# Later, if you want to unsubscribe
client.unsubscribe(subscription_id)

# Always remember to close the connection when done
client.close()
```

## License

This package is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contributing

Feel free to open an issue or submit a pull request if you want to contribute!
