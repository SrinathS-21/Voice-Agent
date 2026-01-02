import { query } from "./_generated/server";
import { v } from "convex/values";

// ============================================
// ANALYTICS - Call statistics and reporting
// ============================================

// Get today's statistics for an organization
export const getTodayStats = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        const todayStart = new Date();
        todayStart.setHours(0, 0, 0, 0);
        const todayStartMs = todayStart.getTime();

        const sessions = await ctx.db
            .query("callSessions")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .filter((q) => q.gte(q.field("startedAt"), todayStartMs))
            .collect();

        const totalCalls = sessions.length;
        const completedCalls = sessions.filter((s) => s.status === "completed").length;
        const failedCalls = sessions.filter((s) => s.status === "failed").length;
        const activeCalls = sessions.filter((s) => s.status === "active").length;

        const completedWithDuration = sessions.filter(
            (s) => s.status === "completed" && s.durationSeconds
        );
        const avgDuration =
            completedWithDuration.length > 0
                ? completedWithDuration.reduce((sum, s) => sum + (s.durationSeconds || 0), 0) /
                completedWithDuration.length
                : 0;

        return {
            today: {
                totalCalls,
                completedCalls,
                failedCalls,
                activeCalls,
                avgDurationSeconds: Math.round(avgDuration),
            },
        };
    },
});

// Get all active calls count (system-wide)
export const getActiveCallsCount = query({
    args: {},
    handler: async (ctx) => {
        const activeCalls = await ctx.db
            .query("callSessions")
            .withIndex("by_status", (q) => q.eq("status", "active"))
            .collect();

        return {
            activeCallsCount: activeCalls.length,
            maxCapacity: 20, // Configurable
            available: Math.max(0, 20 - activeCalls.length),
        };
    },
});

// Get session details with interactions
export const getSessionDetails = query({
    args: { sessionId: v.string() },
    handler: async (ctx, args) => {
        const session = await ctx.db
            .query("callSessions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();

        if (!session) return null;

        const interactions = await ctx.db
            .query("callInteractions")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .order("asc")
            .collect();

        const metrics = await ctx.db
            .query("callMetrics")
            .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
            .unique();

        return {
            session,
            interactions,
            metrics,
        };
    },
});

// Get agent type breakdown for organization
export const getAgentBreakdown = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        const sessions = await ctx.db
            .query("callSessions")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .collect();

        const breakdown: Record<string, number> = {};
        for (const session of sessions) {
            breakdown[session.agentType] = (breakdown[session.agentType] || 0) + 1;
        }

        return breakdown;
    },
});
