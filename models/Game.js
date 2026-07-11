// models/Game.js
const mongoose = require('mongoose');

const gameSchema = new mongoose.Schema({
  name: {
    type: String,
    required: [true, 'Game name is required'],
    unique: true,
    trim: true
  },
  description: {
    type: String,
    trim: true
  },
  category: {
    type: String,
    enum: ['shooter', 'strategy', 'sports', 'racing', 'fighting', 'mobile', 'pc', 'console'],
    required: [true, 'Category is required']
  },
  minPlayers: {
    type: Number,
    default: 1,
    min: 1
  },
  maxPlayers: {
    type: Number,
    default: 100,
    min: 2
  },
  icon: {
    type: String,
    default: ''
  },
  bannerImage: {
    type: String,
    default: ''
  },
  isActive: {
    type: Boolean,
    default: true
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

gameSchema.pre('save', function(next) {
  this.updatedAt = new Date();
  next();
});

module.exports = mongoose.model('Game', gameSchema);