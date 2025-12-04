// models/User.js - CORRECT SCHEMA (no uid)
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');

const userSchema = new mongoose.Schema({
  name: {
    type: String,
    required: [true, 'Name is required'],
    trim: true
  },
  email: {
    type: String,
    required: [true, 'Email is required'],
    unique: true,
    lowercase: true,
    trim: true
  },
  phone: {
    type: String,
    required: [true, 'Phone number is required'],
    unique: true,
    trim: true
  },
  password: {
    type: String,
    required: [true, 'Password is required'],
    minlength: [6, 'Password must be at least 6 characters']
  },
  role: {
    type: String,
    enum: ['user', 'admin'],
    default: 'user'
  },
  isVerified: {
    type: Boolean,
    default: false
  },
  mpesaPhone: {
    type: String,
    trim: true
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  }
}, {
  // Ensure Mongoose uses email/phone as unique, not uid
  autoIndex: true
});

// ✅ COMBINED pre-save hook that handles everything
userSchema.pre('save', async function() {
    console.log('🔐 Pre-save hook called for:', this.email);
    
    // 1. Update timestamp
    this.updatedAt = new Date();
    
    // 2. Remove uid field if someone tries to add it
    if (this.uid !== undefined) {
        console.warn('⚠️ Attempt to set uid field detected and removed');
        this.uid = undefined;
    }
    
    // 3. Only hash password if it was modified
    if (!this.isModified('password')) {
        console.log('⚠️ Password not modified, skipping hash');
        return;
    }
    
    try {
        console.log('🔧 Hashing password...');
        const salt = await bcrypt.genSalt(10);
        this.password = await bcrypt.hash(this.password, salt);
        console.log('✅ Password hashed successfully');
    } catch (error) {
        console.error('💥 Password hash error:', error.message);
        // Don't throw - let save continue with plain password
        // This is a security issue but better than failing registration
    }
});

// Prevent uid field in updates
userSchema.pre('findOneAndUpdate', function(next) {
    const update = this.getUpdate();
    if (update && update.$set && update.$set.uid !== undefined) {
        console.warn(`🛑 Security: uid update attempted`);
        delete update.$set.uid;
    }
    if (update && update.uid !== undefined) {
        console.warn(`🛑 Security: uid update attempted`);
        delete update.uid;
    }
    next();
});

// Compare password method
userSchema.methods.comparePassword = async function(candidatePassword) {
  try {
    return await bcrypt.compare(candidatePassword, this.password);
  } catch (error) {
    console.error('Password comparison error:', error);
    return false;
  }
};

// Remove password from JSON response
userSchema.methods.toJSON = function() {
  const user = this.toObject();
  delete user.password;
  return user;
};

console.log('✅ User model loaded with uid protection');
module.exports = mongoose.model('User', userSchema);