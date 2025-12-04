// routes/payment.js
const express = require('express');
const router = express.Router();
const paypalClient = require('../paypalClient');
const Payment = require('../models/Payment');
const Wallet = require('../models/Wallet');
const Transaction = require('../models/Transaction');

// Create PayPal Order
router.post('/create', async (req, res) => {
  try {
    const { amount, currency = 'USD', userId } = req.body;
    
    if (!amount || !userId) {
      return res.status(400).json({ error: 'amount and userId are required' });
    }

    const orderData = {
      intent: 'CAPTURE',
      purchase_units: [{
        amount: {
          currency_code: currency,
          value: amount.toString()
        },
        description: 'Wallet Top-up'
      }],
      application_context: {
        return_url: process.env.PAYPAL_RETURN_URL || 'http://localhost:5000/api/payments/success',
        cancel_url: process.env.PAYPAL_CANCEL_URL || 'http://localhost:5000/api/payments/cancel'
      }
    };

    const order = await paypalClient.createOrder(orderData);

    if (!order || !order.links) {
      return res.status(500).json({ error: 'PayPal order response missing links' });
    }

    const approvalUrl = order.links.find(link => link.rel === 'approve')?.href;

    if (!approvalUrl) {
      return res.status(500).json({ error: 'Approval URL not found in PayPal response' });
    }

    // Create a pending transaction
    const transaction = await Transaction.create({
      userId: userId,
      type: 'topup',
      amount: parseFloat(amount),
      currency: currency,
      status: 'pending',
      paymentMethod: 'PayPal',
      description: 'PayPal wallet top-up - pending',
      referenceId: order.id
    });

    // Create pending payment record
    await Payment.create({
      userId: userId,
      orderId: order.id,
      amount: parseFloat(amount),
      currency: currency,
      status: 'pending',
      paymentMethod: 'PayPal',
      transactionId: transaction._id,
      metadata: {
        paypalOrderId: order.id,
        approvalUrl: approvalUrl
      }
    });

    res.json({ 
      orderID: order.id, 
      approvalUrl,
      transactionId: transaction._id,
      success: true 
    });
    
  } catch (err) {
    console.error('Create order error:', err.message || err);
    res.status(500).json({ 
      error: 'Failed to create PayPal order',
      details: err.message 
    });
  }
});

// Capture PayPal Order
router.post('/capture/:orderID', async (req, res) => {
  const { orderID } = req.params;

  try {
    const capture = await paypalClient.captureOrder(orderID);

    if (capture.status !== 'COMPLETED') {
      return res.status(400).json({ 
        error: `Payment status is '${capture.status}', expected 'COMPLETED'` 
      });
    }

    // Extract payment info
    const userId = req.body.userId || "test-user";
    const purchaseUnit = capture.purchase_units[0];
    const captureDetails = purchaseUnit.payments.captures[0];
    
    const amount = parseFloat(captureDetails.amount.value);
    const currency = captureDetails.amount.currency_code;
    const paypalTransactionId = captureDetails.id;

    // Find the pending payment record
    let payment = await Payment.findOne({ orderId: orderID });
    
    if (!payment) {
      payment = await Payment.create({
        userId: userId,
        orderId: orderID,
        amount: amount,
        currency: currency,
        status: 'completed',
        paymentMethod: 'PayPal',
        metadata: capture
      });
    } else {
      payment.status = 'completed';
      payment.metadata = capture;
      payment.updatedAt = new Date();
      await payment.save();
    }

    // Find or update transaction record
    let transaction;
    if (payment.transactionId) {
      transaction = await Transaction.findByIdAndUpdate(
        payment.transactionId,
        {
          status: 'completed',
          referenceId: paypalTransactionId,
          description: `PayPal deposit - ${paypalTransactionId}`,
          metadata: capture
        },
        { new: true }
      );
    } else {
      transaction = await Transaction.create({
        userId: userId,
        type: 'topup',
        amount: amount,
        currency: currency,
        status: 'completed',
        paymentMethod: 'PayPal',
        referenceId: paypalTransactionId,
        description: 'PayPal wallet top-up',
        metadata: capture
      });
      
      payment.transactionId = transaction._id;
      await payment.save();
    }

    // Update user's wallet balance
    let wallet = await Wallet.findOne({ userId: payment.userId });
    
    if (!wallet) {
      wallet = new Wallet({ 
        userId: payment.userId, 
        balance: amount,
        currency: currency,
        lastTransactionAt: new Date()
      });
    } else {
      if (wallet.currency !== currency) {
        console.warn(`Currency mismatch: wallet in ${wallet.currency}, payment in ${currency}`);
        wallet.balance += amount;
      } else {
        wallet.balance += amount;
      }
      wallet.lastTransactionAt = new Date();
    }
    
    await wallet.save();

    console.log('✅ PayPal payment processed successfully:', {
      userId: payment.userId,
      amount: amount,
      currency: currency,
      transactionId: paypalTransactionId,
      newBalance: wallet.balance
    });

    res.json({ 
      message: 'Payment captured successfully', 
      success: true,
      data: {
        amount: amount,
        currency: currency,
        transactionId: transaction._id,
        paypalTransactionId: paypalTransactionId,
        walletBalance: wallet.balance
      }
    });
    
  } catch (err) {
    console.error("Capture error:", err.message || err);
    res.status(500).json({ 
      error: "Failed to capture PayPal payment",
      details: err.message 
    });
  }
});

// PayPal success callback
router.get('/success', (req, res) => {
  const { token, PayerID } = req.query;
  res.json({ 
    message: 'Payment successful!',
    token: token,
    payerId: PayerID,
    success: true
  });
});

// PayPal cancel callback
router.get('/cancel', (req, res) => {
  res.json({ 
    message: 'Payment cancelled',
    success: false
  });
});

// Get payment status
router.get('/status/:orderID', async (req, res) => {
  try {
    const { orderID } = req.params;
    
    const payment = await Payment.findOne({ orderId: orderID })
      .populate('transactionId', 'status amount description createdAt');
    
    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    const wallet = await Wallet.findOne({ userId: payment.userId });

    res.json({
      payment: {
        status: payment.status,
        amount: payment.amount,
        currency: payment.currency,
        userId: payment.userId,
        orderId: payment.orderId,
        paymentMethod: payment.paymentMethod,
        createdAt: payment.createdAt,
        updatedAt: payment.updatedAt
      },
      transaction: payment.transactionId,
      walletBalance: wallet ? wallet.balance : 0
    });

  } catch (error) {
    console.error('Error fetching payment status:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's PayPal payment history
router.get('/history/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 50, page = 1 } = req.query;
    
    const payments = await Payment.find({ 
      userId: userId, 
      paymentMethod: 'PayPal' 
    })
      .sort({ createdAt: -1 })
      .limit(parseInt(limit))
      .skip((parseInt(page) - 1) * parseInt(limit))
      .populate('transactionId', 'status description');
    
    const total = await Payment.countDocuments({ 
      userId: userId, 
      paymentMethod: 'PayPal' 
    });

    res.json({
      payments,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / parseInt(limit))
      }
    });

  } catch (error) {
    console.error('Error fetching payment history:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;