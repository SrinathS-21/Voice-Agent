import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// ============================================
// CALL SESSIONS - Voice call tracking
// ============================================

// Create a new call session
export const create = mutation({
    args: {
        sessionId: v.string(),
        organizationId: v.string(),
        phoneNumber: v.string(),
        callType: v.union(v.literal("inbound"), v.literal("outbound")),
        agentType: v.string(),
        config: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const now = Date.now();
        const id = await ctx.db.insert("callSessions", {
            sessionId: args.sessionId,
            organizationId: args.organizationId,
            phoneNumber: args.phoneNumber,
            callType: args.callType,
            agentType: args.agentType,
            status: "active",
            startedAt: now,
            config: args.config,
            createdAt: now,
            updatedAt: now,
        });
        return { _id: id, sessionId: args.sessionId };
    },
});

// Import existing session (for migration)
export const createImported = mutation({
    args: {
        sessionId: v.string(),
        organizationId: v.string(),
        callSid: v.optional(v.string()),
        callType: v.union(v.literal("inbound"), v.literal("outbound")),
        phoneNumber: v.string(),
        agentType: v.string(),
        status: v.union(
            v.literal("active"),
            v.literal("completed"),
            v.literal("failed"),
            v.literal("expired")
        ),
        startedAt: v.number(),
        endedAt: v.optional(v.number()),
        durationSeconds: v.optional(v.number()),
        config: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const existing = await ctx.db
            .query("callSessions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();

        if (existing) return existing._id;

        const id = await ctx.db.insert("callSessions", {
            sessionId: args.sessionId,
            organizationId: args.organizationId,
            callSid: args.callSid,
            callType: args.callType,
            phoneNumber: args.phoneNumber,
            agentType: args.agentType,
            status: args.status,
            startedAt: args.startedAt,
            endedAt: args.endedAt,
            durationSeconds: args.durationSeconds,
            config: args.config,
            createdAt: args.startedAt, // approximate
            updatedAt: args.endedAt || args.startedAt,
        });
        return { _id: id, sessionId: args.sessionId };
    },
});

// Get session by sessionId
export const getBySessionId = query({
    args: { sessionId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callSessions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();
    },
});

// Get session by Twilio call SID
export const getByCallSid = query({
    args: { callSid: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callSessions")
            .withIndex("by_call_sid", (q) => q.eq("callSid", args.callSid))
            .unique();
    },
});

// Update session with Twilio call SID
export const setCallSid = mutation({
    args: {
        sessionId: v.string(),
        callSid: v.string(),
    },
    handler: async (ctx, args) => {
        const session = await ctx.db
            .query("callSessions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();

        if (!session) throw new Error("Session not found");

        await ctx.db.patch(session._id, {
            callSid: args.callSid,
            updatedAt: Date.now(),
        });
    },
});

// Update session status
export const updateStatus = mutation({
    args: {
        sessionId: v.string(),
        status: v.union(
            v.literal("active"),
            v.literal("completed"),
            v.literal("failed"),
            v.literal("expired")
        ),
        endedAt: v.optional(v.number()),
        durationSeconds: v.optional(v.number()),
    },
    handler: async (ctx, args) => {
        const session = await ctx.db
            .query("callSessions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();

        if (!session) throw new Error("Session not found");

        await ctx.db.patch(session._id, {
            status: args.status,
            endedAt: args.endedAt,
            durationSeconds: args.durationSeconds,
            updatedAt: Date.now(),
        });
    },
});

// Get active calls for organization
export const getActiveCalls = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callSessions")
            .withIndex("by_status_and_organization", (q) =>
                q.eq("status", "active").eq("organizationId", args.organizationId)
            )
            .collect();
    },
});

// Get all active calls (system-wide)
export const getAllActiveCalls = query({
    args: {},
    handler: async (ctx) => {
        return await ctx.db
            .query("callSessions")
            .withIndex("by_status", (q) => q.eq("status", "active"))
            .collect();
    },
});

// Get recent sessions for organization
export const getRecentSessions = query({
    args: {
        organizationId: v.string(),
        limit: v.optional(v.number()),
    },
    handler: async (ctx, args) => {
        const limit = args.limit ?? 50;
        return await ctx.db
            .query("callSessions")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .order("desc")
            .take(limit);
    },
});

// List sessions by organization
export const listByOrganization = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callSessions")
            .withIndex("by_organization_id", (q) => q.eq("organizationId", args.organizationId))
            .order("desc")
            .take(100);
    },
});
