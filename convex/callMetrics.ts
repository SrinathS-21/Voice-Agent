import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getBySessionId = query({
    args: { sessionId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("callMetrics")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .collect();
    },
});

export const log = mutation({
    args: {
        sessionId: v.string(),
        organizationId: v.string(),
        latencyMs: v.optional(v.number()),
        audioQualityScore: v.optional(v.number()),
        callCompleted: v.boolean(),
        errorsCount: v.number(),
        functionsCalledCount: v.number(),
        userSatisfied: v.optional(v.boolean()),
        deepgramUsageSeconds: v.optional(v.number()),
    },
    handler: async (ctx, args) => {
        await ctx.db.insert("callMetrics", {
            ...args,
            createdAt: Date.now(),
        });
    },
});
