const paypal = require('@paypal/checkout-server-sdk');
require('dotenv').config();

// Environment setup (Sandbox or Live)
const environment = new paypal.core.SandboxEnvironment(
  process.env.PAYPAL_CLIENT_ID,
  process.env.PAYPAL_CLIENT_SECRET
);

const client = new paypal.core.PayPalHttpClient(environment);

// Create a new order
async function createOrder(orderData) {
  const request = new paypal.orders.OrdersCreateRequest();
  request.requestBody(orderData);

  const response = await client.execute(request);
  return response.result; // contains order ID and approval URL
}

// Capture an existing order
async function captureOrder(orderId) {
  const request = new paypal.orders.OrdersCaptureRequest(orderId);
  request.requestBody({});

  const response = await client.execute(request);
  return response.result; // contains capture confirmation
}

module.exports = {
  createOrder,
  captureOrder
};

