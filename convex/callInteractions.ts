import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// ============================================
// CALL INTERACTIONS - Message and function call logging
// ============================================

// Get all interactions for a session
export const getBySessionId = query({
    args: { sessionId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callInteractions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .order("asc")
            .collect();
    },
});

// Log a user message
export const logUserMessage = mutation({
    args: {
        sessionId: v.string(),
        userInput: v.string(),
    },
    handler: async (ctx, args) => {
        return await ctx.db.insert("callInteractions", {
            sessionId: args.sessionId,
            interactionType: "user_message",
            timestamp: Date.now(),
            userInput: args.userInput,
        });
    },
});

// Log an agent response
export const logAgentResponse = mutation({
    args: {
        sessionId: v.string(),
        agentResponse: v.string(),
    },
    handler: async (ctx, args) => {
        return await ctx.db.insert("callInteractions", {
            sessionId: args.sessionId,
            interactionType: "agent_response",
            timestamp: Date.now(),
            agentResponse: args.agentResponse,
        });
    },
});

// Log a function call
export const logFunctionCall = mutation({
    args: {
        sessionId: v.string(),
        functionName: v.string(),
        functionParams: v.string(),
        functionResult: v.string(),
    },
    handler: async (ctx, args) => {
        return await ctx.db.insert("callInteractions", {
            sessionId: args.sessionId,
            interactionType: "function_call",
            timestamp: Date.now(),
            functionName: args.functionName,
            functionParams: args.functionParams,
            functionResult: args.functionResult,
        });
    },
});
