import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
    args: {
        slug: v.string(),
        name: v.string(),
        billingCustomerId: v.optional(v.string()),
        status: v.union(v.literal("active"), v.literal("inactive")),
        config: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const existing = await ctx.db
            .query("organizations")
            .withIndex("by_slug", (q) => q.eq("slug", args.slug))
            .unique();

        if (existing) {
            return existing._id;
        }

        const id = await ctx.db.insert("organizations", {
            slug: args.slug,
            name: args.name,
            billingCustomerId: args.billingCustomerId,
            status: args.status,
            config: args.config,
            createdAt: Date.now(),
        });
        return id;
    },
});

export const getBySlug = query({
    args: { slug: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("organizations")
            .withIndex("by_slug", (q) => q.eq("slug", args.slug))
            .unique();
    },
});

export const updateConfig = mutation({
    args: { id: v.id("organizations"), config: v.string() },
    handler: async (ctx, args) => {
        await ctx.db.patch(args.id, { config: args.config });
    },
});

export const getById = query({
    args: { id: v.string() },
    handler: async (ctx, args) => {
        // Try to find by Convex ID first
        try {
            // If it's a valid Convex ID format, use db.get
            const doc = await ctx.db.get(args.id as any);
            if (doc) return doc;
        } catch {
            // Not a valid Convex ID, continue
        }

        // Try by slug as fallback
        return await ctx.db
            .query("organizations")
            .withIndex("by_slug", (q) => q.eq("slug", args.id))
            .unique();
    },
});

export const listAll = query({
    args: {},
    handler: async (ctx) => {
        return await ctx.db.query("organizations").collect();
    },
});
