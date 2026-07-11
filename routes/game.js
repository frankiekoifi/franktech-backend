const express = require("express");
const router = express.Router();
const Game = require("../models/Game");

// Add a new game
router.post("/add", async (req, res) => {
  try {
    const { name, platform, description } = req.body;

    const existingGame = await Game.findOne({ name });
    if (existingGame) {
      return res.status(400).json({ error: "Game already exists" });
    }

    const game = new Game({ name, platform, description });
    await game.save();

    res.status(201).json({ message: "Game added", game });
  } catch (error) {
    console.error("Add game error:", error);
    res.status(500).json({ error: "Server error" });
  }
});

// Get all games
router.get("/", async (req, res) => {
  try {
    const games = await Game.find();
    res.status(200).json(games);
  } catch (error) {
    console.error("Get games error:", error);
    res.status(500).json({ error: "Server error" });
  }
});

module.exports = router;
