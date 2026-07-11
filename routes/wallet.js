const express = require("express");
const router = express.Router();
const Wallet = require("../models/Wallet");

// Get wallet balance by user ID
router.get("/balance/:uid", async (req, res) => {
  try {
    const uid = req.params.uid;
    console.log("Requested UID:", uid); // for debugging

    const wallet = await Wallet.findOne({ userId: uid });

    if (!wallet) {
      return res.status(404).json({ error: "Wallet not found" });
    }

    res.status(200).json({ balance: wallet.balance });
  } catch (error) {
    console.error("Wallet balance error:", error);
    res.status(500).json({ error: "Server error" });
  }
});
// ✅ Add money to wallet
router.post("/add", async (req, res) => {
  const { uid, amount } = req.body;

  if (!uid || typeof amount !== "number") {
    return res.status(400).json({ error: "uid and numeric amount are required" });
  }

  try {
    const wallet = await Wallet.findOne({ userId: uid });

    if (!wallet) {
      return res.status(404).json({ error: "Wallet not found" });
    }

    wallet.balance += amount;
    await wallet.save();

    res.status(200).json({ message: "Balance updated", balance: wallet.balance });
  } catch (err) {console.error("Add balance error:", err);
    res.status(500).json({ error: "Server error" });
  }
});
// Withdraw from wallet
router.post("/withdraw", async (req, res) => {
  const { uid, amount } = req.body;

  if (!uid || typeof amount !== "number") {
    return res.status(400).json({ error: "uid and numeric amount are required" });
  }

  try {
    const wallet = await Wallet.findOne({ userId: uid });

    if (!wallet) {
      return res.status(404).json({ error: "Wallet not found" });
    }

    if (wallet.balance < amount) {
      return res.status(400).json({ error: "Insufficient balance" });
    }

    wallet.balance -= amount;
    await wallet.save();

    res.status(200).json({ message: "Withdrawal successful", balance: wallet.balance });
  } catch (err) {
    console.error("Withdraw error:", err);
    res.status(500).json({ error: "Server error" });
  }
});


module.exports = router;

