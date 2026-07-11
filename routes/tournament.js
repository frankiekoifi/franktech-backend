// routes/tournament.js
const express = require("express");
const router = express.Router();
const Tournament = require("../models/Tournament");
const Game = require("../models/Game");
const Wallet = require("../models/Wallet");
const { auth, isAdmin } = require("../middleware/authMiddleware");

// Create a new tournament (Admin/Organizer only)
router.post("/create", auth, async (req, res) => {
  try {
    const { gameId, name, description, entryFee, maxPlayers, scheduledDate, rules } = req.body;
    const userId = req.user._id; // From your auth middleware

    // Validate required fields
    if (!gameId || !name || !entryFee || !maxPlayers || !scheduledDate) {
      return res.status(400).json({ 
        success: false,
        error: "Missing required fields",
        required: ["gameId", "name", "entryFee", "maxPlayers", "scheduledDate"]
      });
    }

    // Check if game exists
    const game = await Game.findById(gameId);
    if (!game) {
      return res.status(404).json({ 
        success: false,
        error: "Game not found" 
      });
    }

    // Create tournament
    const tournament = new Tournament({
      game: gameId,
      name,
      description: description || "",
      entryFee: parseFloat(entryFee),
      maxPlayers: parseInt(maxPlayers),
      scheduledDate: new Date(scheduledDate),
      rules: rules || "",
      createdBy: userId,
      status: 'upcoming'
    });

    await tournament.save();

    // Populate game details for response
    await tournament.populate('game', 'name category icon');

    res.status(201).json({ 
      success: true,
      message: "Tournament created successfully",
      tournament 
    });

  } catch (error) {
    console.error("Create tournament error:", error);
    
    if (error.name === 'ValidationError') {
      return res.status(400).json({ 
        success: false,
        error: "Validation error",
        details: error.message 
      });
    }
    
    res.status(500).json({ 
      success: false,
      error: "Server error",
      message: error.message 
    });
  }
});

// Get all tournaments (Public)
router.get("/", async (req, res) => {
  try {
    const { status, game, page = 1, limit = 10, search } = req.query;
    
    // Build filter
    const filter = {};
    if (status) filter.status = status;
    if (game) filter.game = game;
    if (search) {
      filter.$or = [
        { name: { $regex: search, $options: 'i' } },
        { description: { $regex: search, $options: 'i' } }
      ];
    }
    
    // Pagination
    const skip = (parseInt(page) - 1) * parseInt(limit);
    
    const tournaments = await Tournament.find(filter)
      .populate("game", "name category icon")
      .populate("createdBy", "name email")
      .sort({ scheduledDate: 1 })
      .skip(skip)
      .limit(parseInt(limit));
    
    const total = await Tournament.countDocuments(filter);
    
    res.status(200).json({
      success: true,
      tournaments,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / parseInt(limit))
      }
    });
    
  } catch (error) {
    console.error("Get tournaments error:", error);
    res.status(500).json({ 
      success: false,
      error: "Server error",
      message: error.message 
    });
  }
});

// Get single tournament by ID (Public)
router.get("/:id", async (req, res) => {
  try {
    const tournament = await Tournament.findById(req.params.id)
      .populate("game", "name category description icon bannerImage")
      .populate("players", "name email avatar")
      .populate("createdBy", "name email")
      .populate("winner", "name email")
      .populate("runnerUp", "name email");
    
    if (!tournament) {
      return res.status(404).json({ 
        success: false,
        error: "Tournament not found" 
      });
    }
    
    res.status(200).json({
      success: true,
      tournament
    });
    
  } catch (error) {
    console.error("Get tournament error:", error);
    
    if (error.name === 'CastError') {
      return res.status(400).json({ 
        success: false,
        error: "Invalid tournament ID" 
      });
    }
    
    res.status(500).json({ 
      success: false,
      error: "Server error",
      message: error.message 
    });
  }
});

// Join a tournament (Protected)
router.post('/:id/join', auth, async (req, res) => {
  try {
    const userId = req.user._id;
    const tournamentId = req.params.id;

    // Get tournament
    const tournament = await Tournament.findById(tournamentId);
    if (!tournament) {
      return res.status(404).json({ 
        success: false,
        error: 'Tournament not found' 
      });
    }

    // Check if tournament is joinable
    if (tournament.status !== 'upcoming' && tournament.status !== 'registration') {
      return res.status(400).json({ 
        success: false,
        error: 'Tournament is not accepting registrations' 
      });
    }

    // Check if already joined
    if (tournament.isUserRegistered(userId)) {
      return res.status(400).json({ 
        success: false,
        error: 'Already joined this tournament' 
      });
    }

    // Check if tournament is full
    if (tournament.isFull()) {
      return res.status(400).json({ 
        success: false,
        error: 'Tournament is full' 
      });
    }

    // Check wallet balance
    const wallet = await Wallet.findOne({ userId });
    if (!wallet) {
      return res.status(400).json({ 
        success: false,
        error: 'Wallet not found' 
      });
    }

    if (wallet.balance < tournament.entryFee) {
      return res.status(400).json({ 
        success: false,
        error: 'Insufficient balance',
        required: tournament.entryFee,
        current: wallet.balance
      });
    }

    // Deduct entry fee
    wallet.balance -= tournament.entryFee;
    await wallet.save();

    // Add player to tournament
    await tournament.addPlayer(userId);

    // Update tournament prize pool
    tournament.prizePool = tournament.currentPlayers * tournament.entryFee;
    
    // If tournament reached max players, update status
    if (tournament.isFull()) {
      tournament.status = 'registration';
    }
    
    await tournament.save();

    res.status(200).json({ 
      success: true,
      message: 'Successfully joined tournament',
      tournamentId: tournament._id,
      entryFee: tournament.entryFee,
      newBalance: wallet.balance,
      currentPlayers: tournament.currentPlayers,
      maxPlayers: tournament.maxPlayers
    });

  } catch (error) {
    console.error('Join tournament error:', error);
    
    if (error.message === 'Tournament is full' || error.message === 'User already registered') {
      return res.status(400).json({ 
        success: false,
        error: error.message 
      });
    }
    
    res.status(500).json({ 
      success: false,
      error: 'Server error',
      message: error.message 
    });
  }
});

// Leave a tournament (with refund if before start) - Protected
router.post('/:id/leave', auth, async (req, res) => {
  try {
    const userId = req.user._id;
    const tournamentId = req.params.id;

    const tournament = await Tournament.findById(tournamentId);
    if (!tournament) {
      return res.status(404).json({ 
        success: false,
        error: 'Tournament not found' 
      });
    }

    // Check if user is registered
    if (!tournament.isUserRegistered(userId)) {
      return res.status(400).json({ 
        success: false,
        error: 'Not registered for this tournament' 
      });
    }

    // Check if tournament has started
    const now = new Date();
    if (tournament.startDate && now >= tournament.startDate) {
      return res.status(400).json({ 
        success: false,
        error: 'Cannot leave tournament after it has started' 
      });
    }

    // Refund entry fee
    const wallet = await Wallet.findOne({ userId });
    if (wallet) {
      wallet.balance += tournament.entryFee;
      await wallet.save();
    }

    // Remove player
    await tournament.removePlayer(userId);

    res.status(200).json({ 
      success: true,
      message: 'Successfully left tournament',
      refunded: tournament.entryFee,
      newBalance: wallet?.balance
    });

  } catch (error) {
    console.error('Leave tournament error:', error);
    res.status(500).json({ 
      success: false,
      error: 'Server error',
      message: error.message 
    });
  }
});

// Get user's tournaments (Protected)
router.get('/user/mytournaments', auth, async (req, res) => {
  try {
    const userId = req.user._id;
    
    const tournaments = await Tournament.find({ players: userId })
      .populate('game', 'name icon')
      .populate('createdBy', 'name email')
      .sort({ scheduledDate: -1 });
    
    res.status(200).json({
      success: true,
      count: tournaments.length,
      tournaments
    });
    
  } catch (error) {
    console.error('Get user tournaments error:', error);
    res.status(500).json({ 
      success: false,
      error: 'Server error',
      message: error.message 
    });
  }
});

// Get tournaments created by user (Protected)
router.get('/user/created', auth, async (req, res) => {
  try {
    const userId = req.user._id;
    
    const tournaments = await Tournament.find({ createdBy: userId })
      .populate('game', 'name icon')
      .populate('players', 'name email')
      .sort({ createdAt: -1 });
    
    res.status(200).json({
      success: true,
      count: tournaments.length,
      tournaments
    });
    
  } catch (error) {
    console.error('Get created tournaments error:', error);
    res.status(500).json({ 
      success: false,
      error: 'Server error',
      message: error.message 
    });
  }
});

// Admin: Update tournament status
router.patch('/:id/status', auth, isAdmin, async (req, res) => {
  try {
    const { status } = req.body;
    const validStatuses = ['upcoming', 'registration', 'ongoing', 'completed', 'cancelled'];
    
    if (!status || !validStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid status',
        validStatuses
      });
    }
    
    const tournament = await Tournament.findById(req.params.id);
    if (!tournament) {
      return res.status(404).json({
        success: false,
        error: 'Tournament not found'
      });
    }
    
    tournament.status = status;
    
    // Set start/end dates based on status
    const now = new Date();
    if (status === 'ongoing' && !tournament.startDate) {
      tournament.startDate = now;
    } else if (status === 'completed' && !tournament.endDate) {
      tournament.endDate = now;
    }
    
    await tournament.save();
    
    res.status(200).json({
      success: true,
      message: `Tournament status updated to ${status}`,
      tournament
    });
    
  } catch (error) {
    console.error('Update status error:', error);
    res.status(500).json({
      success: false,
      error: 'Server error',
      message: error.message
    });
  }
});

// Admin: Set tournament winner
router.post('/:id/set-winner', auth, isAdmin, async (req, res) => {
  try {
    const { winnerId, runnerUpId } = req.body;
    const tournamentId = req.params.id;
    
    const tournament = await Tournament.findById(tournamentId);
    if (!tournament) {
      return res.status(404).json({
        success: false,
        error: 'Tournament not found'
      });
    }
    
    // Check if users are tournament participants
    if (winnerId && !tournament.players.includes(winnerId)) {
      return res.status(400).json({
        success: false,
        error: 'Winner must be a tournament participant'
      });
    }
    
    if (runnerUpId && !tournament.players.includes(runnerUpId)) {
      return res.status(400).json({
        success: false,
        error: 'Runner-up must be a tournament participant'
      });
    }
    
    // Update tournament
    if (winnerId) tournament.winner = winnerId;
    if (runnerUpId) tournament.runnerUp = runnerUpId;
    tournament.status = 'completed';
    tournament.endDate = new Date();
    
    await tournament.save();
    
    // Distribute prizes (you'll need to implement this)
    // await distributePrizes(tournament);
    
    res.status(200).json({
      success: true,
      message: 'Tournament results updated',
      tournament
    });
    
  } catch (error) {
    console.error('Set winner error:', error);
    res.status(500).json({
      success: false,
      error: 'Server error',
      message: error.message
    });
  }
});
// Get available games for tournaments (Public)
router.get('/games/available', async (req, res) => {
  try {
    const games = await Game.find({ isActive: true })
      .select('name category icon description minPlayers maxPlayers bannerImage')
      .sort({ name: 1 });
    
    res.status(200).json({
      success: true,
      count: games.length,
      games: games.map(game => ({
        id: game._id,
        name: game.name,
        category: game.category,
        icon: game.icon,
        description: game.description,
        minPlayers: game.minPlayers,
        maxPlayers: game.maxPlayers,
        bannerImage: game.bannerImage
      }))
    });
    
  } catch (error) {
    console.error('Get available games error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to get games',
      message: error.message
    });
  }
});

module.exports = router;