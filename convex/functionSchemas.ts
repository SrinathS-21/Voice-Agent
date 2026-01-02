import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

/**
 * Function Schemas - Dynamic function definitions for organizations
 * Supports multi-domain voice agents with customizable functions
 */

// Create a new function schema
export const create = mutation({
    args: {
        organizationId: v.string(),
        domain: v.string(),
        functionName: v.string(),
        description: v.string(),
        parameters: v.string(), // JSON schema
        handlerType: v.union(
            v.literal("vector_search"),
            v.literal("convex_query"),
            v.literal("webhook"),
            v.literal("static")
        ),
        handlerConfig: v.string(), // JSON config
        isActive: v.boolean(),
        createdAt: v.number(),
        updatedAt: v.number(),
    },
    handler: async (ctx, args) => {
        const id = await ctx.db.insert("functionSchemas", args);
        return id;
    },
});

// Update a function schema
export const update = mutation({
    args: {
        id: v.id("functionSchemas"),
        description: v.optional(v.string()),
        parameters: v.optional(v.string()),
        handlerType: v.optional(v.union(
            v.literal("vector_search"),
            v.literal("convex_query"),
            v.literal("webhook"),
            v.literal("static")
        )),
        handlerConfig: v.optional(v.string()),
        isActive: v.optional(v.boolean()),
        updatedAt: v.number(),
    },
    handler: async (ctx, args) => {
        const { id, ...updates } = args;
        await ctx.db.patch(id, updates);
        return id;
    },
});

// Remove a function schema
export const remove = mutation({
    args: {
        id: v.id("functionSchemas"),
    },
    handler: async (ctx, args) => {
        await ctx.db.delete(args.id);
        return true;
    },
});

// Get function schema by organization and name
export const getByName = query({
    args: {
        organizationId: v.string(),
        functionName: v.string(),
    },
    handler: async (ctx, args) => {
        const result = await ctx.db
            .query("functionSchemas")
            .withIndex("by_function_name", (q) =>
                q.eq("organizationId", args.organizationId)
                 .eq("functionName", args.functionName)
            )
            .first();
        return result;
    },
});

// Get all function schemas for an organization
export const getByOrganization = query({
    args: {
        organizationId: v.string(),
    },
    handler: async (ctx, args) => {
        const results = await ctx.db
            .query("functionSchemas")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .collect();
        return results;
    },
});

// Get all function schemas for a domain (across all organizations)
export const getByDomain = query({
    args: {
        domain: v.string(),
    },
    handler: async (ctx, args) => {
        const results = await ctx.db
            .query("functionSchemas")
            .withIndex("by_domain", (q) =>
                q.eq("domain", args.domain)
            )
            .collect();
        return results;
    },
});

// Get active functions for an organization
export const getActiveFunctions = query({
    args: {
        organizationId: v.string(),
    },
    handler: async (ctx, args) => {
        const results = await ctx.db
            .query("functionSchemas")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .filter((q) => q.eq(q.field("isActive"), true))
            .collect();
        return results;
    },
});

// Bulk create function schemas (for initial setup)
export const bulkCreate = mutation({
    args: {
        schemas: v.array(v.object({
            organizationId: v.string(),
            domain: v.string(),
            functionName: v.string(),
            description: v.string(),
            parameters: v.string(),
            handlerType: v.union(
                v.literal("vector_search"),
                v.literal("convex_query"),
                v.literal("webhook"),
                v.literal("static")
            ),
            handlerConfig: v.string(),
            isActive: v.boolean(),
            createdAt: v.number(),
            updatedAt: v.number(),
        })),
    },
    handler: async (ctx, args) => {
        const ids = [];
        for (const schema of args.schemas) {
            const id = await ctx.db.insert("functionSchemas", schema);
            ids.push(id);
        }
        return ids;
    },
});

// Deactivate all functions for an organization
export const deactivateAll = mutation({
    args: {
        organizationId: v.string(),
    },
    handler: async (ctx, args) => {
        const functions = await ctx.db
            .query("functionSchemas")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .filter((q) => q.eq(q.field("isActive"), true))
            .collect();

        const now = Date.now();
        for (const func of functions) {
            await ctx.db.patch(func._id, { 
                isActive: false, 
                updatedAt: now 
            });
        }

        return functions.length;
    },
});

// Delete all functions for an organization
export const deleteByOrganization = mutation({
    args: {
        organizationId: v.string(),
    },
    handler: async (ctx, args) => {
        const functions = await ctx.db
            .query("functionSchemas")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .collect();

        for (const func of functions) {
            await ctx.db.delete(func._id);
        }

        return functions.length;
    },
});
