require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const helmet = require('helmet');

// Enhanced CORS configuration for ngrok and local development
const corsOptions = {
  origin: function (origin, callback) {
    // Allow requests with no origin (like mobile apps, curl, postman)
    if (!origin) return callback(null, true);
    
    const allowedOrigins = [
      'https://honourably-charitable-alvina.ngrok-free.dev',
      /^https?:\/\/.*\.ngrok-free\.dev$/,
      'http://localhost:64039',
      'http://localhost:3000',
      'http://localhost:5000',
      'http://127.0.0.1:64039',
      'http://127.0.0.1:5000',
      'http://0.0.0.0:5000'
    ];
    
    if (allowedOrigins.some(allowed => {
      if (typeof allowed === 'string') {
        return origin === allowed;
      } else if (allowed instanceof RegExp) {
        return allowed.test(origin);
      }
      return false;
    })) {
      callback(null, true);
    } else {
      console.log(`CORS blocked origin: ${origin}`);
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'Accept', 'Origin'],
  exposedHeaders: ['Content-Length', 'X-Request-Id'],
  maxAge: 86400
};
if (process.env.NODE_ENV === 'production') {
  app.use(helmet()); // Security headers
  app.set('trust proxy', 1); // Trust proxy for rate limiting
  
  // Rate limiting for production
  const limiter = require('express-rate-limit')({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
  });
  app.use('/api/', limiter);
}

app.use(cors(corsOptions));
app.options('*', cors(corsOptions));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Request logging
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.originalUrl}`);
  console.log(`   From: ${req.ip} | Origin: ${req.headers.origin || 'none'}`);
  next();
});

console.log('Starting Franktech Backend...');
console.log(`Root directory: ${__dirname}`);
console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
console.log(`MPESA_CALLBACK_URL: ${process.env.MPESA_CALLBACK_URL}`);

// Route loading
const loadRoute = (routePath, routePrefix) => {
  try {
    const route = require(routePath);
    app.use(routePrefix, route);
    console.log(`${routePrefix} routes loaded`);
    return true;
  } catch (error) {
    console.error(`Failed to load ${routePrefix}: ${error.message}`);
    return false;
  }
};

console.log('\nLoading routes...');
loadRoute('./routes/auth', '/api/auth');
loadRoute('./routes/wallet', '/api/wallet');
loadRoute('./routes/game', '/api/games');
loadRoute('./routes/tournament', '/api/tournaments');
loadRoute('./routes/payment', '/api/payment');
loadRoute('./routes/mpesa', '/api/mpesa');
console.log('All routes loaded\n');

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// MongoDB connection
if (process.env.MONGO_URI) {
  console.log('Connecting to MongoDB...');
  
  mongoose.set('strictQuery', true);
  
  mongoose.connect(process.env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
    socketTimeoutMS: 45000,
    family: 4
  })
  .then(() => {
    console.log('MongoDB connected successfully');
  })
  .catch(err => {
    console.error('MongoDB connection failed:', err.message);
    console.log('Server will continue without database');
  });
} else {
  console.log('MONGO_URI not found in environment variables');
}

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'franktech-backend',
    version: '1.0.0',
    environment: process.env.NODE_ENV || 'development'
  });
});

// Test endpoint
app.get('/api/test', (req, res) => {
  res.json({
    message: 'Test endpoint working!',
    serverTime: new Date().toISOString(),
    ngrokUrl: 'https://honourably-charitable-alvina.ngrok-free.dev',
    callbackUrl: process.env.MPESA_CALLBACK_URL || 'Not set'
  });
});

// M-Pesa test endpoint
app.get('/api/mpesa/test', (req, res) => {
  res.json({
    status: 'M-Pesa API Test',
    environment: process.env.MPESA_ENVIRONMENT || 'Not set',
    shortcode: process.env.MPESA_SHORTCODE || 'Not set',
    callbackUrl: process.env.MPESA_CALLBACK_URL || 'Not set',
    callbackConfigured: !!process.env.MPESA_CALLBACK_URL,
    timestamp: new Date().toISOString()
  });
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'Welcome to Franktech Gaming Backend API',
    endpoints: {
      auth: '/api/auth/*',
      wallet: '/api/wallet/*',
      games: '/api/games/*',
      tournaments: '/api/tournaments/*',
      payment: '/api/payment/*',
      mpesa: '/api/mpesa/*',
      system: ['/api/health', '/api/test', '/']
    },
    serverInfo: {
      port: PORT,
      environment: process.env.NODE_ENV || 'development',
      time: new Date().toISOString(),
      ngrokUrl: 'https://honourably-charitable-alvina.ngrok-free.dev'
    }
  });
});

// 404 handler
app.use((req, res) => {
  console.log(`404: Route not found: ${req.method} ${req.originalUrl}`);
  
  res.status(404).json({
    error: 'Not Found',
    message: `Route ${req.method} ${req.originalUrl} does not exist`,
    availableRoutes: {
      auth: '/api/auth/*',
      wallet: '/api/wallet/*',
      games: '/api/games/*',
      tournaments: '/api/tournaments/*',
      payment: '/api/payment/*',
      mpesa: '/api/mpesa/*',
      system: ['/api/health', '/api/test', '/']
    },
    timestamp: new Date().toISOString()
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('Global Error Handler:');
  console.error(`   URL: ${req.method} ${req.originalUrl}`);
  console.error(`   Error: ${err.message}`);
  
  const errorResponse = {
    error: 'Internal Server Error',
    message: 'Something went wrong on the server',
    timestamp: new Date().toISOString()
  };
  
  if (process.env.NODE_ENV !== 'production') {
    errorResponse.details = err.message;
  }
  
  res.status(err.status || 500).json(errorResponse);
});

// Start server with all network interfaces
const server = app.listen(PORT, '0.0.0.0', () => {
  const address = server.address();
  const host = address.address === '::' ? '0.0.0.0' : address.address;
  
  console.log('\nServer is running!');
  console.log(`Local: http://localhost:${PORT}`);
  console.log(`Network: http://${host}:${PORT}`);
  console.log(`External (ngrok): https://honourably-charitable-alvina.ngrok-free.dev`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`Started: ${new Date().toLocaleTimeString()}`);
  console.log('\nAvailable endpoints:');
  console.log(`   Local: http://localhost:${PORT}/api/health`);
  console.log(`   Network: http://${host}:${PORT}/api/health`);
  console.log(`   Ngrok: https://honourably-charitable-alvina.ngrok-free.dev/api/health`);
  console.log(`   Test: http://localhost:${PORT}/api/test`);
  console.log(`   M-Pesa Test: http://localhost:${PORT}/api/mpesa/test`);
  console.log('\nReady for requests!');
  console.log('\nIMPORTANT FOR M-PESA:');
  console.log(`   Make sure .env has: MPESA_CALLBACK_URL=https://honourably-charitable-alvina.ngrok-free.dev/api/mpesa/callback`);
  console.log('');
});