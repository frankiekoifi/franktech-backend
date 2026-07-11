// routes/mpesa.js
require('dotenv').config();
const express = require('express');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const router = express.Router();

// Models
const Payment = require('../models/Payment');
const Wallet = require('../models/Wallet');
const Transaction = require('../models/Transaction');

// Security middleware for M-Pesa routes
router.use((req, res, next) => {
  // Add security headers
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  next();
});

// ==================== HELPER FUNCTIONS ====================

// Helper: validate phone number format (2547XXXXXXXX)
function validatePhoneNumber(phone) {
  if (!phone) return false;
  const cleaned = phone.toString().trim();
  return /^2547\d{8}$/.test(cleaned);
}

// Helper: validate amount (positive number)
function validateAmount(amount) {
  const num = parseFloat(amount);
  return !isNaN(num) && num > 0 && num <= 70000; // M-Pesa max is 70,000
}

// Helper: get OAuth token from Safaricom
async function getAccessToken() {
  try {
    const consumerKey = process.env.MPESA_CONSUMER_KEY;
    const consumerSecret = process.env.MPESA_CONSUMER_SECRET;
    
    if (!consumerKey || !consumerSecret) {
      throw new Error('MPESA_CONSUMER_KEY or MPESA_CONSUMER_SECRET is missing');
    }

    console.log('🔑 Getting access token with:', {
      keyLength: consumerKey?.length,
      secretLength: consumerSecret?.length
    });

    const auth = Buffer.from(`${consumerKey}:${consumerSecret}`).toString('base64');
    
    const response = await axios.get(
      'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
      { 
        headers: { 
          'Authorization': `Basic ${auth}`,
          'Content-Type': 'application/json'
        },
        timeout: 10000 // 10 seconds timeout
      }
    ); 
    
    console.log('✅ Access token received successfully');
    return response.data.access_token;
    
  } catch (error) {
    console.error('❌ Access token error:', error.response?.data || error.message);
    throw new Error('Failed to fetch access token: ' + error.message);
  }
}

// Helper: generate timestamp YYYYMMDDHHmmss
function getTimestamp() {
  const d = new Date();
  const YYYY = d.getFullYear().toString();
  const MM = String(d.getMonth() + 1).padStart(2, '0');
  const DD = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${YYYY}${MM}${DD}${hh}${mm}${ss}`;
}

// Helper: create with retry logic
async function createWithRetry(model, data, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await model.create(data);
    } catch (error) {
      if (i === retries - 1) throw error;
      console.log(`⚠️ Retry ${i + 1} for ${model.modelName} creation`);
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
}

// Helper: verify callback signature (production)
function verifyCallbackSignature(req) {
  if (process.env.NODE_ENV !== 'production') return true;
  
  const signature = req.headers['x-safaricom-signature'];
  const timestamp = req.headers['x-safaricom-timestamp'];
  
  if (!signature || !timestamp) {
    console.warn('⚠️ Missing Safaricom signature headers');
    return false;
  }
  
  // TODO: Implement actual signature verification
  // Compare with your passkey and timestamp
  return true;
}

// Helper: validate M-Pesa configuration
function validateMpesaConfig() {
  const required = [
    'MPESA_CONSUMER_KEY',
    'MPESA_CONSUMER_SECRET', 
    'MPESA_SHORTCODE',
    'MPESA_PASSKEY',
    'MPESA_CALLBACK_URL'
  ];
  
  const missing = required.filter(key => !process.env[key]);
  
  if (missing.length > 0) {
    console.error('❌ Missing M-Pesa environment variables:', missing);
    return false;
  }
  
  // Validate callback URL format
  const callbackUrl = process.env.MPESA_CALLBACK_URL;
  if (process.env.NODE_ENV === 'production' && !callbackUrl.startsWith('https://')) {
    console.error('❌ MPESA_CALLBACK_URL must use HTTPS in production');
    return false;
  }
  
  return true;
}

// ==================== ROUTES ====================

// Health check and config validation
router.get('/config-check', (req, res) => {
  const configValid = validateMpesaConfig();
  res.json({ 
    mpesaConfigured: configValid,
    timestamp: new Date(),
    environment: process.env.NODE_ENV || 'development'
  });
});

// Test endpoint
router.get('/test', (req, res) => {
  console.log('✅✅✅ /api/mpesa/test endpoint HIT!');
  res.json({ 
    message: 'M-Pesa route is working!', 
    time: new Date(),
    env: {
      hasConsumerKey: !!process.env.MPESA_CONSUMER_KEY,
      hasConsumerSecret: !!process.env.MPESA_CONSUMER_SECRET,
      hasShortcode: !!process.env.MPESA_SHORTCODE,
      hasPasskey: !!process.env.MPESA_PASSKEY,
      callbackUrl: process.env.MPESA_CALLBACK_URL
    }
  });
});

// Test POST endpoint
router.post('/test-post', (req, res) => {
  console.log('✅✅✅ /api/mpesa/test-post endpoint HIT!');
  console.log('📦 Request body:', req.body);
  console.log('🌐 Request origin:', req.headers.origin);
  res.json({ 
    message: 'POST is working!', 
    received: req.body,
    time: new Date() 
  });
});

// Route: initiate M-Pesa STK Push
router.post('/pay', async (req, res) => {
  const requestId = uuidv4();
  console.log(`\n🎯🎯🎯 M-Pesa /pay route TRIGGERED! Request ID: ${requestId} 🎯🎯🎯`);
  console.log('📅 Time:', new Date().toISOString());
  console.log('📡 Request from IP:', req.ip);
  console.log('🌐 Origin:', req.headers.origin);
  console.log('👤 User-Agent:', req.headers['user-agent']);
  console.log('📦 Request Body:', JSON.stringify(req.body, null, 2));
  console.log('🔍 Environment Check:', {
    MPESA_CONSUMER_KEY: process.env.MPESA_CONSUMER_KEY ? `Present (${process.env.MPESA_CONSUMER_KEY.length} chars)` : 'MISSING',
    MPESA_CONSUMER_SECRET: process.env.MPESA_CONSUMER_SECRET ? `Present (${process.env.MPESA_CONSUMER_SECRET.length} chars)` : 'MISSING',
    MPESA_SHORTCODE: process.env.MPESA_SHORTCODE || 'MISSING',
    MPESA_PASSKEY: process.env.MPESA_PASSKEY ? `Present (${process.env.MPESA_PASSKEY.length} chars)` : 'MISSING',
    MPESA_CALLBACK_URL: process.env.MPESA_CALLBACK_URL || 'MISSING'
  });
  console.log('----------------------------------------\n');

  const { phoneNumber, amount, userId } = req.body;

  // Enhanced validation
  if (!phoneNumber || !amount || !userId) {
    console.log('❌ Validation failed: Missing required fields');
    return res.status(400).json({ 
      error: 'Missing required fields',
      details: 'phoneNumber, amount and userId are required'
    });
  }

  if (!validatePhoneNumber(phoneNumber)) {
    return res.status(400).json({ 
      error: 'Invalid phone number',
      details: 'Phone must be in format: 2547XXXXXXXX (e.g., 254708374149)'
    });
  }

  if (!validateAmount(amount)) {
    return res.status(400).json({ 
      error: 'Invalid amount',
      details: 'Amount must be a positive number between 1 and 70,000'
    });
  }

  console.log('✅ Validation passed:', { phoneNumber, amount, userId, requestId });

  try {
    console.log('🔑 Step 1: Getting access token...');
    const token = await getAccessToken();
    console.log('✅ Access token received');
    
    console.log('🕒 Step 2: Generating timestamp and password...');
    const timestamp = getTimestamp();
    console.log('✅ Timestamp:', timestamp);
    
    const shortcode = process.env.MPESA_SHORTCODE;
    const passkey = process.env.MPESA_PASSKEY;
    console.log('🔐 Password components:', { 
      shortcode, 
      passkeyLength: passkey?.length,
      timestamp 
    });
    
    const password = Buffer.from(shortcode + passkey + timestamp).toString('base64');
    console.log('✅ Password generated');

    const payload = {
      BusinessShortCode: shortcode,
      Password: password,
      Timestamp: timestamp,
      TransactionType: 'CustomerPayBillOnline',
      Amount: amount,
      PartyA: phoneNumber,
      PartyB: shortcode,
      PhoneNumber: phoneNumber,
      CallBackURL: process.env.MPESA_CALLBACK_URL,
      AccountReference: userId,
      TransactionDesc: 'Wallet Top-up'
    };

    console.log('📤 Step 3: Sending to Safaricom...');
    console.log('📦 Safaricom payload:', payload);

    const response = await axios.post(
      'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
      payload,
      { 
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        timeout: 15000 // 15 seconds timeout
      }
    );

    console.log('✅ Safaricom response:', response.data);

    // Create a pending transaction with retry
    console.log('💾 Step 4: Creating transaction record...');
    const transaction = await createWithRetry(Transaction, {
      userId: userId,
      type: 'topup',
      amount: amount,
      currency: 'KES',
      status: 'pending',
      paymentMethod: 'M-Pesa',
      description: 'M-Pesa wallet top-up - pending',
      referenceId: requestId,
      metadata: { requestId }
    });
    console.log('✅ Transaction created:', transaction._id);

    // Create pending payment record with retry
    console.log('💾 Step 5: Creating payment record...');
    await createWithRetry(Payment, {
      checkoutRequestId: response.data.CheckoutRequestID,
      userId: userId,
      amount: amount,
      phoneNumber: phoneNumber,
      status: 'pending',
      paymentMethod: 'M-Pesa',
      currency: 'KES',
      transactionId: transaction._id,
      requestId: requestId,
      metadata: {
        merchantRequestId: response.data.MerchantRequestID,
        checkoutRequestId: response.data.CheckoutRequestID,
        requestId: requestId,
        safaricomResponse: response.data
      }
    });
    console.log('✅ Payment record created');

    console.log('🎉🎉🎉 Payment flow COMPLETED successfully! 🎉🎉🎉\n');

    return res.json({ 
      message: 'STK Push initiated', 
      data: response.data,
      transactionId: transaction._id,
      checkoutRequestId: response.data.CheckoutRequestID,
      requestId: requestId,
      success: true 
    });
    
  } catch (err) {
    console.error('💥 M-Pesa STK Push error:', {
      message: err.message,
      stack: err.stack,
      response: err.response?.data,
      requestId: requestId
    });
    
    // Different error messages based on error type
    let errorMessage = 'Failed to initiate M-Pesa payment';
    let statusCode = 500;
    
    if (err.code === 'ECONNABORTED') {
      errorMessage = 'Request timeout. Please try again.';
    } else if (err.response?.status === 401) {
      errorMessage = 'Authentication failed. Check your M-Pesa credentials.';
      statusCode = 401;
    } else if (err.response?.status === 400) {
      errorMessage = 'Invalid request parameters.';
      statusCode = 400;
    }
    
    return res.status(statusCode).json({ 
      error: errorMessage,
      details: err.response?.data || err.message,
      requestId: requestId
    });
  }
});

// Route: callback to receive payment confirmation from Safaricom
router.post('/callback', async (req, res) => {
  console.log('\n📝📝📝 M-Pesa callback received at:', new Date().toISOString());
  
  try {
    // Verify callback signature in production
    if (!verifyCallbackSignature(req)) {
      console.error('❌ Invalid callback signature');
      return res.status(401).json({ 
        ResultCode: 1, 
        ResultDesc: "Unauthorized callback" 
      });
    }

    const callbackData = req.body;
    console.log('📦 Callback data:', JSON.stringify(callbackData, null, 2));

    if (!callbackData || !callbackData.Body) {
      console.error('❌ Invalid callback structure: Missing Body');
      return res.status(200).json({ 
        ResultCode: 0, // Always return 0 to Safaricom
        ResultDesc: "Success" 
      });
    }

    const stkCall = callbackData.Body.stkCallback;
    if (!stkCall) {
      console.error('❌ Invalid callback: Missing stkCallback');
      return res.status(200).json({ 
        ResultCode: 0,
        ResultDesc: "Success" 
      });
    }

    const { ResultCode, ResultDesc, CheckoutRequestID, CallbackMetadata } = stkCall;
    console.log('🔍 Callback details:', { ResultCode, ResultDesc, CheckoutRequestID });

    // Always respond to Safaricom immediately to avoid timeouts
    const sendSuccessResponse = () => {
      return res.status(200).json({
        ResultCode: 0,
        ResultDesc: "Success"
      });
    };

    // Find the payment record
    const payment = await Payment.findOne({ checkoutRequestId: CheckoutRequestID });
    
    if (!payment) {
      console.error('❌ Payment record not found for checkout:', CheckoutRequestID);
      return sendSuccessResponse();
    }

    console.log('💰 Payment found:', {
      userId: payment.userId,
      amount: payment.amount,
      status: payment.status
    });

    // If payment failed
    if (ResultCode !== 0) {
      console.warn('⚠️ Payment failed:', { 
        userId: payment.userId,
        amount: payment.amount,
        ResultCode, 
        ResultDesc 
      });

      // Update payment status
      await Payment.findByIdAndUpdate(payment._id, {
        status: 'failed',
        failureReason: ResultDesc,
        updatedAt: new Date()
      });

      // Update transaction status
      if (payment.transactionId) {
        await Transaction.findByIdAndUpdate(payment.transactionId, {
          status: 'failed',
          description: `M-Pesa payment failed: ${ResultDesc}`
        });
      }

      return sendSuccessResponse();
    }

    // Payment successful - process metadata
    if (!CallbackMetadata || !CallbackMetadata.Item) {
      console.error('❌ Successful payment but missing metadata');
      return sendSuccessResponse();
    }

    // Extract payment details from metadata
    const metadata = CallbackMetadata.Item;
    const extractMetadata = (name) => {
      const item = metadata.find(i => i.Name === name);
      return item ? item.Value : null;
    };

    const paymentDetails = {
      amount: extractMetadata('Amount'),
      mpesaReceiptNumber: extractMetadata('MpesaReceiptNumber'),
      transactionDate: extractMetadata('TransactionDate'),
      phoneNumber: extractMetadata('PhoneNumber'),
      accountReference: extractMetadata('AccountReference')
    };

    console.log('💰 Payment details extracted:', paymentDetails);

    // Validate required payment details
    if (!paymentDetails.mpesaReceiptNumber || !paymentDetails.amount) {
      console.error('❌ Missing critical payment details:', paymentDetails);
      return sendSuccessResponse();
    }

    // Update payment record
    const updatedPayment = await Payment.findByIdAndUpdate(
      payment._id,
      {
        status: 'completed',
        mpesaReceiptNumber: paymentDetails.mpesaReceiptNumber,
        transactionDate: paymentDetails.transactionDate,
        phoneNumber: paymentDetails.phoneNumber || payment.phoneNumber,
        amount: paymentDetails.amount,
        updatedAt: new Date(),
        completedAt: new Date(),
        metadata: { 
          ...payment.metadata, 
          callback: callbackData,
          paymentDetails: paymentDetails
        }
      },
      { new: true }
    );

    console.log('✅ Payment updated:', updatedPayment._id);

    // Update transaction record
    const transaction = await Transaction.findByIdAndUpdate(
      payment.transactionId,
      {
        status: 'completed',
        referenceId: paymentDetails.mpesaReceiptNumber,
        description: `M-Pesa deposit - ${paymentDetails.mpesaReceiptNumber}`,
        amount: paymentDetails.amount,
        metadata: paymentDetails
      },
      { new: true }
    );

    console.log('✅ Transaction updated:', transaction._id);

    // Update user's wallet balance
    let wallet = await Wallet.findOne({ userId: payment.userId });
    
    if (!wallet) {
      wallet = new Wallet({ 
        userId: payment.userId, 
        balance: parseFloat(paymentDetails.amount),
        currency: 'KES',
        lastTransactionAt: new Date(),
        lastTransactionId: transaction._id
      });
    } else {
      wallet.balance += parseFloat(paymentDetails.amount);
      wallet.lastTransactionAt = new Date();
      wallet.lastTransactionId = transaction._id;
    }
    
    await wallet.save();

    console.log('✅ Wallet updated:', {
      userId: payment.userId,
      newBalance: wallet.balance,
      transactionAmount: paymentDetails.amount
    });

    console.log('🎉🎉🎉 M-Pesa payment processed SUCCESSFULLY! 🎉🎉🎉\n');

    return sendSuccessResponse();

  } catch (error) {
    console.error('💥 Callback processing error:', {
      message: error.message,
      stack: error.stack
    });
    
    // Always return success to Safaricom even on our errors
    return res.status(200).json({
      ResultCode: 0,
      ResultDesc: "Success"
    });
  }
});

// Route: check payment status
router.get('/payment-status/:checkoutRequestId', async (req, res) => {
  try {
    const { checkoutRequestId } = req.params;
    
    console.log('🔍 Checking payment status for:', checkoutRequestId);
    
    const payment = await Payment.findOne({ checkoutRequestId })
      .populate('transactionId', 'status amount description createdAt currency');
    
    if (!payment) {
      return res.status(404).json({ 
        error: 'Payment not found',
        checkoutRequestId 
      });
    }

    // Get wallet balance
    const wallet = await Wallet.findOne({ userId: payment.userId });

    res.json({
      payment: {
        status: payment.status,
        amount: payment.amount,
        userId: payment.userId,
        phoneNumber: payment.phoneNumber,
        mpesaReceiptNumber: payment.mpesaReceiptNumber,
        checkoutRequestId: payment.checkoutRequestId,
        createdAt: payment.createdAt,
        updatedAt: payment.updatedAt,
        completedAt: payment.completedAt,
        failureReason: payment.failureReason
      },
      transaction: payment.transactionId,
      wallet: {
        balance: wallet ? wallet.balance : 0,
        currency: wallet ? wallet.currency : 'KES'
      },
      timestamp: new Date()
    });

  } catch (error) {
    console.error('💥 Error fetching payment status:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: error.message 
    });
  }
});

// Route: get user transaction history
router.get('/transactions/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 50, page = 1, type } = req.query;
    
    console.log('📋 Fetching transactions for user:', userId);
    
    // Build query
    const query = { userId };
    if (type) query.type = type;
    
    const transactions = await Transaction.find(query)
      .sort({ createdAt: -1 })
      .limit(parseInt(limit))
      .skip((parseInt(page) - 1) * parseInt(limit));
    
    const total = await Transaction.countDocuments(query);

    // Get wallet balance
    const wallet = await Wallet.findOne({ userId });

    res.json({
      transactions,
      walletBalance: wallet ? wallet.balance : 0,
      walletCurrency: wallet ? wallet.currency : 'KES',
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / parseInt(limit))
      },
      summary: {
        totalTransactions: total,
        totalPages: Math.ceil(total / parseInt(limit)),
        currentPage: parseInt(page)
      }
    });

  } catch (error) {
    console.error('💥 Error fetching transactions:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: error.message 
    });
  }
});

// Route: get user wallet info
router.get('/wallet/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    
    let wallet = await Wallet.findOne({ userId });
    
    if (!wallet) {
      // Create empty wallet if doesn't exist
      wallet = new Wallet({ 
        userId, 
        balance: 0,
        currency: 'KES'
      });
      await wallet.save();
    }
    
    // Get recent transactions
    const recentTransactions = await Transaction.find({ userId })
      .sort({ createdAt: -1 })
      .limit(10);
    
    res.json({
      wallet: {
        balance: wallet.balance,
        currency: wallet.currency,
        userId: wallet.userId,
        lastTransactionAt: wallet.lastTransactionAt,
        createdAt: wallet.createdAt,
        updatedAt: wallet.updatedAt
      },
      recentTransactions,
      timestamp: new Date()
    });

  } catch (error) {
    console.error('💥 Error fetching wallet:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: error.message 
    });
  }
});

// ⭐⭐⭐ MAKE SURE THIS LINE IS AT THE END ⭐⭐⭐
module.exports = router;