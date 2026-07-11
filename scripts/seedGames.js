// scripts/seedGames.js
require('dotenv').config();
const mongoose = require('mongoose');
const Game = require('../models/Game');

async function seedGames() {
  try {
    console.log('🎮 Seeding games database...');
    
    // Connect to MongoDB
    await mongoose.connect(process.env.MONGO_URI || process.env.MONGODB_URI);
    console.log('✅ Connected to MongoDB');
    
    // Sample games data
    const games = [
      {
        name: 'PUBG Mobile',
        description: 'Battle royale mobile game',
        category: 'shooter',
        icon: '🎮',
        minPlayers: 1,
        maxPlayers: 100
      },
      {
        name: 'Call of Duty Mobile',
        description: 'First-person shooter mobile game',
        category: 'shooter',
        icon: '🔫',
        minPlayers: 1,
        maxPlayers: 10
      },
      {
        name: 'Free Fire',
        description: 'Battle royale survival shooter',
        category: 'shooter',
        icon: '🔥',
        minPlayers: 1,
        maxPlayers: 50
      },
      {
        name: 'FIFA Mobile',
        description: 'Football/soccer simulation game',
        category: 'sports',
        icon: '⚽',
        minPlayers: 1,
        maxPlayers: 2
      },
      {
        name: 'NBA 2K Mobile',
        description: 'Basketball simulation game',
        category: 'sports',
        icon: '🏀',
        minPlayers: 1,
        maxPlayers: 2
      },
      {
        name: 'Mobile Legends',
        description: 'Multiplayer online battle arena',
        category: 'strategy',
        icon: '⚔️',
        minPlayers: 5,
        maxPlayers: 5
      },
      {
        name: 'Clash Royale',
        description: 'Real-time strategy card game',
        category: 'strategy',
        icon: '👑',
        minPlayers: 1,
        maxPlayers: 2
      },
      {
        name: 'Asphalt 9',
        description: 'Arcade racing game',
        category: 'racing',
        icon: '🏎️',
        minPlayers: 1,
        maxPlayers: 8
      }
    ];
    
    // Clear existing games (optional)
    await Game.deleteMany({});
    console.log('🗑️  Cleared existing games');
    
    // Insert games
    await Game.insertMany(games);
    console.log(`✅ Added ${games.length} games to database`);
    
    // Show what was added
    const allGames = await Game.find({}, 'name category icon');
    console.log('\n📋 Games in database:');
    allGames.forEach(game => {
      console.log(`  ${game.icon} ${game.name} (${game.category})`);
    });
    
    console.log('\n🎮 Game seeding completed!');
    process.exit(0);
    
  } catch (error) {
    console.error('❌ Error seeding games:', error);
    process.exit(1);
  }
}

seedGames();