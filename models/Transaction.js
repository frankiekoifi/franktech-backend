// models/Transaction.js
const mongoose = require('mongoose');

const transactionSchema = new mongoose.Schema({
  userId: { type: String, required: true },
  type: { 
    type: String, 
    enum: ['deposit', 'withdrawal', 'payment', 'refund', 'topup', 'game_entry', 'prize'],
    required: true 
  },
  amount: { type: Number, required: true },
  currency: { type: String, default: 'KES' },
  description: { type: String },
  status: { 
    type: String, 
    enum: ['pending', 'completed', 'failed', 'cancelled'],
    default: 'pending'
  },
  referenceId: { type: String },
  paymentMethod: { type: String },
  metadata: { type: Object }
}, {
  timestamps: true
});

// Indexes for faster queries
transactionSchema.index({ userId: 1 });
transactionSchema.index({ type: 1 });
transactionSchema.index({ status: 1 });
transactionSchema.index({ referenceId: 1 });
transactionSchema.index({ createdAt: -1 });

module.exports = mongoose.model('Transaction', transactionSchema);