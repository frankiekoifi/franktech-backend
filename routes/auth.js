// routes/auth.js - VERSION 2 (Add User Model)
const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');

// Test endpoint
router.get('/test', (req, res) => {
  res.json({ 
    message: 'Auth API is working!',
    timestamp: new Date().toISOString()
  });
});

// Register endpoint - WITH USER MODEL
router.post('/register', async (req, res) => {
  try {
    console.log('📝 Register request received:', req.body);
    
    const { name, email, phone, password } = req.body;
    
    // Basic validation
    if (!name || !email || !phone || !password) {
      return res.status(400).json({
        error: 'Validation failed',
        message: 'All fields are required'
      });
    }
    
    // Check if User model loads
    let User;
    try {
      User = require('../models/User');
      console.log('✅ User model loaded successfully');
    } catch (modelError) {
      console.error('❌ Failed to load User model:', modelError.message);
      return res.status(500).json({
        error: 'Server configuration error',
        message: 'User model not available',
        details: modelError.message
      });
    }
    
    // Check if user exists
    const existingUser = await User.findOne({ 
      $or: [{ email }, { phone }] 
    });
    
    if (existingUser) {
      return res.status(400).json({
        error: 'User already exists',
        field: existingUser.email === email ? 'email' : 'phone'
      });
    }
    
    // Create user
    const user = new User({
      name,
      email,
      phone,
      password,
      mpesaPhone: phone
    });
    
    await user.save();
    console.log('✅ User created:', user._id);
    
    // Generate token
    const token = jwt.sign(
      { userId: user._id },
      process.env.JWT_SECRET || 'your-secret-key-change-in-production',
      { expiresIn: '7d' }
    );
    
    res.status(201).json({
      message: 'User registered successfully',
      user: user.toJSON(),
      token
    });
    
  } catch (error) {
    console.error('❌ Registration error:', error);
    res.status(500).json({
      error: 'Registration failed',
      details: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
});

// Login endpoint - ACTUAL IMPLEMENTATION
router.post('/login', async (req, res) => {
  try {
    console.log('🔐 Login request received:', req.body);
    
    const { email, password } = req.body;
    
    if (!email || !password) {
      return res.status(400).json({
        error: 'Validation failed',
        message: 'Email and password are required'
      });
    }
    
    // Load User model
    let User;
    try {
      User = require('../models/User');
      console.log('✅ User model loaded for login');
    } catch (modelError) {
      console.error('❌ Failed to load User model:', modelError.message);
      return res.status(500).json({
        error: 'Server configuration error',
        message: 'User model not available'
      });
    }
    
    // Find user by email
    const user = await User.findOne({ email: email.toLowerCase().trim() });
    
    if (!user) {
      console.log('❌ Login failed: User not found for email:', email);
      return res.status(401).json({
        error: 'Authentication failed',
        message: 'Invalid email or password'
      });
    }
    
    // Verify password
    const isPasswordValid = await user.comparePassword(password);
    
    if (!isPasswordValid) {
      console.log('❌ Login failed: Invalid password for email:', email);
      return res.status(401).json({
        error: 'Authentication failed',
        message: 'Invalid email or password'
      });
    }
    
    console.log('✅ Login successful for user:', user.email);
    
    // Generate token
    const token = jwt.sign(
      { userId: user._id },
      process.env.JWT_SECRET || 'your-secret-key-change-in-production',
      { expiresIn: '7d' }
    );
    
    // Return user data (excluding password)
    const userResponse = user.toJSON();
    
    res.status(200).json({
      message: 'Login successful',
      user: userResponse,
      token
    });
    
  } catch (error) {
    console.error('❌ Login error:', error);
    res.status(500).json({
      error: 'Login failed',
      details: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
});

// Get user profile (protected)
router.get('/profile', async (req, res) => {
  try {
    // Get token from Authorization header
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'No token provided'
      });
    }
    
    const token = authHeader.split(' ')[1];
    
    // Verify token
    const decoded = jwt.verify(
      token,
      process.env.JWT_SECRET || 'your-secret-key-change-in-production'
    );
    
    // Load User model
    const User = require('../models/User');
    
    // Get user
    const user = await User.findById(decoded.userId);
    
    if (!user) {
      return res.status(404).json({
        error: 'User not found',
        message: 'User does not exist'
      });
    }
    
    res.status(200).json({
      message: 'Profile retrieved successfully',
      user: user.toJSON()
    });
    
  } catch (error) {
    console.error('❌ Profile error:', error);
    
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({
        error: 'Invalid token',
        message: 'Token is invalid or expired'
      });
    }
    
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({
        error: 'Token expired',
        message: 'Please login again'
      });
    }
    
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

console.log('✅ Auth router V2 initialized');
module.exports = router;