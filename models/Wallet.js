// models/Wallet.js - FIXED
const mongoose = require('mongoose');

const walletSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true,
    unique: true
  },
  balance: {
    type: Number,
    default: 0,
    min: 0
  },
  currency: {
    type: String,
    default: 'KES'
  },
  lastTransactionAt: {
    type: Date
  },
  lastTransactionId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Transaction'
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  }
});

// ✅ ONLY ONE pre-save middleware (REMOVE THE OTHER ONE)
walletSchema.pre('save', function() {
  this.updatedAt = new Date();
  // No next() needed
});

// Create wallet automatically when user registers
walletSchema.statics.createForUser = async function(userId) {
  try {
    const wallet = new this({
      userId: userId,
      balance: 0,
      currency: 'KES'
    });
    await wallet.save();
    return wallet;
  } catch (error) {
    console.error('Error creating wallet:', error);
    throw error;
  }
};

module.exports = mongoose.model('Wallet', walletSchema);