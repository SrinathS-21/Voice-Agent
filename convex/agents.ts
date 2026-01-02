import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
    args: {
        organizationId: v.string(),
        name: v.string(),
        role: v.optional(v.string()),
        systemPrompt: v.string(),
        config: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const id = await ctx.db.insert("agents", {
            organizationId: args.organizationId,
            name: args.name,
            role: args.role,
            systemPrompt: args.systemPrompt,
            config: args.config,
            createdAt: Date.now(),
            updatedAt: Date.now(),
        });
        return id;
    },
});

export const listByOrganization = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("agents")
            .withIndex("by_organization_id", (q) => q.eq("organizationId", args.organizationId))
            .collect();
    },
});

export const updateConfig = mutation({
    args: { id: v.id("agents"), config: v.string() },
    handler: async (ctx, args) => {
        await ctx.db.patch(args.id, { config: args.config, updatedAt: Date.now() });
    },
});

export const get = query({
    args: { id: v.id("agents") },
    handler: async (ctx, args) => {
        return await ctx.db.get(args.id);
    },
});
