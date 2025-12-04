// models/Payment.js
const mongoose = require('mongoose');

const paymentSchema = new mongoose.Schema({
  // Common fields
  userId: { type: String, required: true },
  amount: { type: Number, required: true },
  currency: { type: String, default: 'KES' },
  status: { 
    type: String, 
    enum: ['pending', 'completed', 'failed', 'cancelled'],
    default: 'pending'
  },
  paymentMethod: { 
    type: String, 
    enum: ['M-Pesa', 'PayPal', 'Card', 'Bank Transfer'],
    required: true 
  },
  failureReason: { type: String },
  
  // Payment method specific fields
  orderId: { type: String },
  checkoutRequestId: { type: String },
  phoneNumber: { type: String },
  mpesaReceiptNumber: { type: String },
  transactionDate: { type: String },
  
  // Transaction reference
  transactionId: { type: mongoose.Schema.Types.ObjectId, ref: 'Transaction' },
  
  // Metadata
  metadata: { type: Object }
}, {
  timestamps: true
});

// Add indexes
paymentSchema.index({ checkoutRequestId: 1 });
paymentSchema.index({ orderId: 1 });
paymentSchema.index({ userId: 1 });
paymentSchema.index({ status: 1 });
paymentSchema.index({ paymentMethod: 1 });

module.exports = mongoose.model('Payment', paymentSchema);