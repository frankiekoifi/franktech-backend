// models/Tournament.js - FIXED VERSION
const mongoose = require('mongoose');

const tournamentSchema = new mongoose.Schema({
  name: {
    type: String,
    required: [true, 'Tournament name is required'],
    trim: true
  },
  game: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Game',
    required: [true, 'Game is required']
  },
  description: {
    type: String,
    trim: true
  },
  entryFee: {
    type: Number,
    required: [true, 'Entry fee is required'],
    min: [0, 'Entry fee cannot be negative']
  },
  prizePool: {
    type: Number,
    default: 0
  },
  maxPlayers: {
    type: Number,
    required: [true, 'Maximum players is required'],
    min: [2, 'Minimum 2 players required']
  },
  currentPlayers: {
    type: Number,
    default: 0
  },
  players: [{
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User'
  }],
  status: {
    type: String,
    enum: ['upcoming', 'registration', 'ongoing', 'completed', 'cancelled'],
    default: 'upcoming'
  },
  scheduledDate: {
    type: Date,
    required: [true, 'Scheduled date is required']
  },
  startDate: {
    type: Date
  },
  endDate: {
    type: Date
  },
  rules: {
    type: String,
    trim: true
  },
  createdBy: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  winner: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User'
  },
  runnerUp: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User'
  },
  isPrivate: {
    type: Boolean,
    default: false
  },
  password: {
    type: String,
    select: false
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
  timestamps: true // Mongoose automatically manages createdAt and updatedAt
});

// ✅ FIXED: Simple pre-save hook WITHOUT next parameter
tournamentSchema.pre('save', function() {
  // Only update prize pool if relevant fields changed
  if (this.isModified('currentPlayers') || this.isModified('entryFee')) {
    this.prizePool = this.currentPlayers * this.entryFee;
  }
  
  // Note: We don't update updatedAt here because timestamps: true does it automatically
  // this.updatedAt = new Date(); // Remove this line
});

// Check if tournament is full
tournamentSchema.methods.isFull = function() {
  return this.currentPlayers >= this.maxPlayers;
};

// Check if user is registered
tournamentSchema.methods.isUserRegistered = function(userId) {
  return this.players.includes(userId);
};

// Add player to tournament
tournamentSchema.methods.addPlayer = async function(userId) {
  if (this.isFull()) {
    throw new Error('Tournament is full');
  }
  
  if (this.isUserRegistered(userId)) {
    throw new Error('User already registered');
  }
  
  this.players.push(userId);
  this.currentPlayers += 1;
  
  return this.save();
};

// Remove player from tournament
tournamentSchema.methods.removePlayer = async function(userId) {
  const playerIndex = this.players.indexOf(userId);
  
  if (playerIndex === -1) {
    throw new Error('User not registered');
  }
  
  this.players.splice(playerIndex, 1);
  this.currentPlayers = Math.max(0, this.currentPlayers - 1);
  
  return this.save();
};

// Calculate prize distribution
tournamentSchema.methods.calculatePrizes = function() {
  const total = this.prizePool;
  return {
    first: total * 0.6,
    second: total * 0.3,
    third: total * 0.1
  };
};

module.exports = mongoose.model('Tournament', tournamentSchema);