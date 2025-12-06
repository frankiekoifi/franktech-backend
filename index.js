require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const helmet = require('helmet');

// ========== BULLETPROOF CORS FIX ==========
// This will allow ALL Flutter development origins
const cors = require('cors');

// Simple CORS - allow everything for now
app.use(cors({
  origin: true,  // Allow ALL origins
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'Accept', 'Origin', 'X-Requested-With'],
  exposedHeaders: ['Authorization'],
  maxAge: 86400
}));

// Handle preflight explicitly
app.options('*', cors());

// Manual logging middleware to see what's happening
app.use((req, res, next) => {
  const origin = req.headers.origin || 'none';
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  console.log(`   Origin: ${origin}`);
  console.log(`   User-Agent: ${req.headers['user-agent']?.substring(0, 50) || 'unknown'}...`);
  
  // Manually set CORS headers as backup
  if (origin !== 'none') {
    res.header('Access-Control-Allow-Origin', origin);
    res.header('Access-Control-Allow-Credentials', 'true');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept, Origin, X-Requested-With');
  }
  
  // Handle OPTIONS preflight
  if (req.method === 'OPTIONS') {
    console.log('✅ Handling OPTIONS preflight');
    return res.status(200).end();
  }
  
  next();
});

// ========== SECURITY & MIDDLEWARE ==========
if (process.env.NODE_ENV === 'production') {
  app.use(helmet({
    // Configure helmet to work with your frontend
    contentSecurityPolicy: false, // You can configure this later
    crossOriginResourcePolicy: { policy: "cross-origin" }
  }));
  app.set('trust proxy', 1);
  
  const limiter = require('express-rate-limit')({
    windowMs: 15 * 60 * 1000,
    max: 100
  });
  app.use('/api/', limiter);
}

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Request logging
app.use((req, res, next) => {
  console.log(`\n${new Date().toISOString()} ${req.method} ${req.originalUrl}`);
  console.log(`   From: ${req.ip} | Origin: ${req.headers.origin || 'none'}`);
  console.log(`   User-Agent: ${req.headers['user-agent'] || 'unknown'}`);
  next();
});

console.log('🚀 Starting Franktech Backend...');
console.log(`📁 Root: ${__dirname}`);
console.log(`⚙️  Environment: ${process.env.NODE_ENV || 'development'}`);
console.log(`🔒 CORS: ALL origins allowed`);

// ========== DEBUG ENDPOINT ==========
app.get('/api/debug', (req, res) => {
  res.json({
    message: 'Debug endpoint working',
    yourOrigin: req.headers.origin || 'none',
    yourIP: req.ip,
    headers: req.headers,
    cors: 'ENABLED - All origins allowed',
    timestamp: new Date().toISOString()
  });
});

app.options('/api/debug', (req, res) => {
  res.status(200).end();
});

// ========== ROUTE LOADING ==========
const loadRoute = (routePath, routePrefix) => {
  try {
    const route = require(routePath);
    app.use(routePrefix, route);
    console.log(`✅ ${routePrefix} routes loaded`);
    return true;
  } catch (error) {
    console.error(`❌ Failed to load ${routePrefix}: ${error.message}`);
    return false;
  }
};

console.log('\n📦 Loading routes...');
loadRoute('./routes/auth', '/api/auth');
loadRoute('./routes/wallet', '/api/wallet');
loadRoute('./routes/game', '/api/games');
loadRoute('./routes/tournament', '/api/tournaments');
loadRoute('./routes/payment', '/api/payment');
loadRoute('./routes/mpesa', '/api/mpesa');
console.log('✅ All routes loaded\n');

// ========== STATIC FILES ==========
app.use(express.static(path.join(__dirname, 'public')));

// ========== DATABASE CONNECTION ==========
if (process.env.MONGO_URI) {
  console.log('🔌 Connecting to MongoDB...');
  
  mongoose.set('strictQuery', true);
  
  mongoose.connect(process.env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
    socketTimeoutMS: 45000,
    family: 4
  })
  .then(() => {
    console.log('✅ MongoDB connected successfully');
  })
  .catch(err => {
    console.error('❌ MongoDB connection failed:', err.message);
    console.log('⚠️ Server will continue without database');
  });
} else {
  console.log('⚠️ MONGO_URI not found in environment variables');
}

// ========== API ENDPOINTS ==========

// Health check with detailed CORS info
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: 'franktech-backend',
    version: '1.0.0',
    environment: process.env.NODE_ENV || 'development',
    cors: {
      allowed: true,
      yourOrigin: req.headers.origin || 'none',
      credentials: true,
      message: 'ALL origins allowed'
    },
    endpoints: {
      auth: '/api/auth/*',
      wallet: '/api/wallet/*',
      games: '/api/games/*',
      tournaments: '/api/tournaments/*',
      payment: '/api/payment/*',
      mpesa: '/api/mpesa/*',
      debug: '/api/debug'
    }
  });
});

// Enhanced CORS test endpoint
app.get('/api/cors-test', (req, res) => {
  res.json({
    message: '🎉 CORS test successful!',
    yourRequest: {
      origin: req.headers.origin || 'No origin header',
      method: req.method,
      ip: req.ip
    },
    serverCors: {
      status: 'ALL origins allowed',
      credentials: true,
      timestamp: new Date().toISOString()
    },
    note: 'If you can see this, CORS is working!'
  });
});

// OPTIONS test endpoint
app.options('/api/cors-test', (req, res) => {
  console.log('✅ CORS test OPTIONS called from:', req.headers.origin);
  res.status(200).json({ 
    message: 'OPTIONS preflight OK',
    corsConfigured: true 
  });
});

// Flutter-specific test endpoint
app.post('/api/flutter-test', (req, res) => {
  console.log('📱 Flutter test request received');
  res.json({
    success: true,
    message: 'Flutter connection successful!',
    receivedData: req.body,
    headers: req.headers,
    cors: 'Working correctly',
    timestamp: new Date().toISOString()
  });
});

app.options('/api/flutter-test', (req, res) => {
  res.status(200).end();
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'Welcome to Franktech Gaming Backend API',
    documentation: 'This API supports Flutter Web applications',
    cors: 'ALL origins allowed for development',
    timestamp: new Date().toISOString(),
    testEndpoints: [
      '/api/health',
      '/api/cors-test',
      '/api/debug',
      '/api/flutter-test (POST)'
    ],
    apiEndpoints: {
      auth: '/api/auth/*',
      wallet: '/api/wallet/*',
      games: '/api/games/*',
      tournaments: '/api/tournaments/*',
      payment: '/api/payment/*',
      mpesa: '/api/mpesa/*'
    }
  });
});

// ========== ERROR HANDLING ==========

// 404 handler
app.use((req, res) => {
  console.log(`❌ 404: ${req.method} ${req.originalUrl}`);
  
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
      system: ['/api/health', '/api/cors-test', '/api/debug', '/api/flutter-test', '/']
    },
    timestamp: new Date().toISOString()
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('\n🔥 Global Error Handler:');
  console.error(`   URL: ${req.method} ${req.originalUrl}`);
  console.error(`   Origin: ${req.headers.origin || 'none'}`);
  console.error(`   Error: ${err.message}`);
  
  const errorResponse = {
    error: 'Internal Server Error',
    message: 'Something went wrong on the server',
    timestamp: new Date().toISOString(),
    path: req.originalUrl
  };
  
  if (process.env.NODE_ENV !== 'production') {
    errorResponse.details = err.message;
    errorResponse.stack = err.stack;
  }
  
  res.status(err.status || 500).json(errorResponse);
});

// ========== START SERVER ==========
const server = app.listen(PORT, '0.0.0.0', () => {
  const address = server.address();
  const host = address.address === '::' ? '0.0.0.0' : address.address;
  
  console.log('\n' + '='.repeat(60));
  console.log('🚀 FRANKTECH BACKEND SERVER STARTED');
  console.log('='.repeat(60));
  console.log(`📡 Local: http://localhost:${PORT}`);
  console.log(`🌐 Network: http://${host}:${PORT}`);
  console.log(`🔗 Render: https://franktech-backend.onrender.com`);
  console.log(`⚙️  Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`🔒 CORS: ALL origins allowed (Development Mode)`);
  console.log(`📱 Flutter: ANY localhost or 127.0.0.1 port will work`);
  console.log(`⏰ Started: ${new Date().toLocaleTimeString()}`);
  console.log('='.repeat(60));
  console.log('\n📋 Test endpoints:');
  console.log(`   Health: https://franktech-backend.onrender.com/api/health`);
  console.log(`   Debug: https://franktech-backend.onrender.com/api/debug`);
  console.log(`   CORS Test: https://franktech-backend.onrender.com/api/cors-test`);
  console.log(`   Flutter Test: POST to https://franktech-backend.onrender.com/api/flutter-test`);
  console.log('\n✅ Ready for Flutter web requests!');
  console.log('='.repeat(60) + '\n');
});