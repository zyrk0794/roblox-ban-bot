const express = require('express');
const mongoose = require('mongoose');
const axios = require('axios');
const cors = require('cors');
require('dotenv').config();

const app = express();
app.use(express.json());
app.use(cors());

const MONGODB_URI = process.env.MONGODB_URI;
mongoose.connect(MONGODB_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true
}).catch(err => console.error("DB Error:", err));

const actionSchema = new mongoose.Schema({
    roblox_username: String,
    roblox_id: Number,
    action_type: String,
    reason: String,
    action_by: String,
    user_id: Number,
    guild_id: Number,
    date: { type: Date, default: Date.now },
    active: { type: Boolean, default: true },
    duration: Number,
    expires_at: Date
});

const Action = mongoose.model('Action', actionSchema);

async function getRobloxUserId(username) {
    try {
        const response = await axios.get(`https://users.roblox.com/v1/usernames/users`, {
            params: { usernames: [username] },
            headers: { 'User-Agent': 'Mozilla/5.0' }
        });
        return response.data.data[0]?.id || null;
    } catch {
        return null;
    }
}

async function getUserByUsername(username) {
    try {
        const response = await axios.get(`https://users.roblox.com/v1/usernames/users`, {
            params: { usernames: [username] }
        });
        return response.data.data[0] || null;
    } catch {
        return null;
    }
}

app.get('/health', (req, res) => {
    res.json({ status: 'OK', timestamp: new Date() });
});

app.post('/api/ban', async (req, res) => {
    try {
        const { username, reason, banned_by, user_id, guild_id, duration } = req.body;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur Roblox non trouvé' });
        
        const existing = await Action.findOne({ 
            roblox_id: user.id, 
            action_type: 'ban',
            active: true 
        });
        
        if (existing) return res.status(400).json({ error: 'Utilisateur déjà banni' });
        
        const action = new Action({
            roblox_username: user.name,
            roblox_id: user.id,
            action_type: 'ban',
            reason: reason || 'Pas de raison',
            action_by: banned_by,
            user_id,
            guild_id,
            duration,
            expires_at: duration ? new Date(Date.now() + duration * 24 * 60 * 60 * 1000) : null
        });
        
        await action.save();
        res.json({ success: true, message: `${user.name} banni`, id: action._id });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.post('/api/unban', async (req, res) => {
    try {
        const { username } = req.body;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const ban = await Action.findOne({ 
            roblox_id: user.id, 
            action_type: 'ban',
            active: true 
        });
        
        if (!ban) return res.status(404).json({ error: 'Utilisateur non banni' });
        
        ban.active = false;
        await ban.save();
        res.json({ success: true, message: `${user.name} débanni` });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.post('/api/kick', async (req, res) => {
    try {
        const { username, reason, kicked_by, user_id, guild_id } = req.body;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const action = new Action({
            roblox_username: user.name,
            roblox_id: user.id,
            action_type: 'kick',
            reason: reason || 'Pas de raison',
            action_by: kicked_by,
            user_id,
            guild_id
        });
        
        await action.save();
        res.json({ success: true, message: `${user.name} expulsé` });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.post('/api/mute', async (req, res) => {
    try {
        const { username, duration, reason, muted_by, user_id, guild_id } = req.body;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const existing = await Action.findOne({
            roblox_id: user.id,
            action_type: 'mute',
            active: true
        });
        
        if (existing) return res.status(400).json({ error: 'Utilisateur déjà rendu muet' });
        
        const action = new Action({
            roblox_username: user.name,
            roblox_id: user.id,
            action_type: 'mute',
            reason: reason || 'Pas de raison',
            action_by: muted_by,
            user_id,
            guild_id,
            duration,
            expires_at: new Date(Date.now() + duration * 60 * 1000)
        });
        
        await action.save();
        res.json({ success: true, message: `${user.name} rendu muet`, duration });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.post('/api/warn', async (req, res) => {
    try {
        const { username, reason, warned_by, user_id, guild_id } = req.body;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const action = new Action({
            roblox_username: user.name,
            roblox_id: user.id,
            action_type: 'warn',
            reason: reason || 'Pas de raison',
            action_by: warned_by,
            user_id,
            guild_id
        });
        
        await action.save();
        
        const totalWarns = await Action.countDocuments({
            roblox_id: user.id,
            action_type: 'warn'
        });
        
        res.json({ success: true, message: 'Avertissement ajouté', total_warns: totalWarns });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.get('/api/check-ban/:username', async (req, res) => {
    try {
        const { username } = req.params;
        
        const user = await getUserByUsername(username);
        if (!user) return res.json({ is_banned: false, error: 'Utilisateur non trouvé' });
        
        const ban = await Action.findOne({ 
            roblox_id: user.id, 
            action_type: 'ban',
            active: true,
            $or: [
                { expires_at: null },
                { expires_at: { $gt: new Date() } }
            ]
        });
        
        if (ban) {
            res.json({
                is_banned: true,
                reason: ban.reason,
                date: ban.date,
                banned_by: ban.action_by,
                unban_date: ban.expires_at
            });
        } else {
            res.json({ is_banned: false });
        }
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.get('/api/warns/:username', async (req, res) => {
    try {
        const { username } = req.params;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const warns = await Action.find({
            roblox_id: user.id,
            action_type: 'warn'
        }).sort({ date: -1 });
        
        res.json({ warns });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.get('/api/history/:username', async (req, res) => {
    try {
        const { username } = req.params;
        
        const user = await getUserByUsername(username);
        if (!user) return res.status(404).json({ error: 'Utilisateur non trouvé' });
        
        const history = await Action.find({ roblox_id: user.id }).sort({ date: -1 });
        
        res.json({ history });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.get('/api/bans', async (req, res) => {
    try {
        const bans = await Action.find({ 
            action_type: 'ban',
            active: true,
            $or: [
                { expires_at: null },
                { expires_at: { $gt: new Date() } }
            ]
        }).sort({ date: -1 });
        
        res.json({ bans });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

app.get('/api/stats', async (req, res) => {
    try {
        const total_bans = await Action.countDocuments({ action_type: 'ban', active: true });
        const total_kicks = await Action.countDocuments({ action_type: 'kick' });
        const total_mutes = await Action.countDocuments({ action_type: 'mute', active: true });
        const total_warns = await Action.countDocuments({ action_type: 'warn' });
        
        res.json({ total_bans, total_kicks, total_mutes, total_warns });
    } catch (error) {
        res.status(500).json({ error: 'Erreur serveur' });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Server ${PORT}`));

setInterval(async () => {
    try {
        await Action.updateMany(
            { expires_at: { $lt: new Date() }, active: true },
            { active: false }
        );
    } catch (error) {
        console.error('Auto-expire error:', error);
    }
}, 60000);
