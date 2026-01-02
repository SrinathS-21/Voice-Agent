import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// ============================================
// PHONE CONFIGS - Multi-tenant phone mapping
// ============================================

// Create a new phone config
export const create = mutation({
    args: {
        phoneNumber: v.string(),
        organizationId: v.string(),
        jobType: v.string(),
        configJson: v.string(),
        agentId: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        // Check if phone number already exists
        const existing = await ctx.db
            .query("phoneConfigs")
            .withIndex("by_phone_number", (q) => q.eq("phoneNumber", args.phoneNumber))
            .unique();

        if (existing) {
            throw new Error(`Phone number ${args.phoneNumber} already configured`);
        }

        const now = Date.now();
        const id = await ctx.db.insert("phoneConfigs", {
            phoneNumber: args.phoneNumber,
            organizationId: args.organizationId,
            jobType: args.jobType,
            configJson: args.configJson,
            agentId: args.agentId,
            isActive: true,
            createdAt: now,
            updatedAt: now,
        });
        return { _id: id, phoneNumber: args.phoneNumber };
    },
});

// Get phone config by phone number
export const getByPhoneNumber = query({
    args: { phoneNumber: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("phoneConfigs")
            .withIndex("by_phone_number", (q) => q.eq("phoneNumber", args.phoneNumber))
            .filter((q) => q.eq(q.field("isActive"), true))
            .unique();
    },
});

// Update phone config
export const update = mutation({
    args: {
        phoneNumber: v.string(),
        jobType: v.optional(v.string()),
        configJson: v.optional(v.string()),
        agentId: v.optional(v.string()),
        organizationId: v.optional(v.string()),
        isActive: v.optional(v.boolean()),
    },
    handler: async (ctx, args) => {
        const config = await ctx.db
            .query("phoneConfigs")
            .withIndex("by_phone_number", (q) => q.eq("phoneNumber", args.phoneNumber))
            .unique();

        if (!config) {
            throw new Error(`Phone config not found: ${args.phoneNumber}`);
        }

        const updates: Record<string, unknown> = { updatedAt: Date.now() };
        if (args.jobType !== undefined) updates.jobType = args.jobType;
        if (args.configJson !== undefined) updates.configJson = args.configJson;
        if (args.agentId !== undefined) updates.agentId = args.agentId;
        if (args.organizationId !== undefined) updates.organizationId = args.organizationId;
        if (args.isActive !== undefined) updates.isActive = args.isActive;

        await ctx.db.patch(config._id, updates);
        return { success: true };
    },
});

// Delete (soft delete by setting isActive = false)
export const deactivate = mutation({
    args: { phoneNumber: v.string() },
    handler: async (ctx, args) => {
        const config = await ctx.db
            .query("phoneConfigs")
            .withIndex("by_phone_number", (q) => q.eq("phoneNumber", args.phoneNumber))
            .unique();

        if (!config) {
            throw new Error(`Phone config not found: ${args.phoneNumber}`);
        }

        await ctx.db.patch(config._id, {
            isActive: false,
            updatedAt: Date.now(),
        });
        return { success: true };
    },
});

// List all phone configs for organization
export const listByOrganization = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("phoneConfigs")
            .withIndex("by_organization_id", (q) =>
                q.eq("organizationId", args.organizationId)
            )
            .filter((q) => q.eq(q.field("isActive"), true))
            .collect();
    },
});

// List all active phone configs
export const listAll = query({
    args: {},
    handler: async (ctx) => {
        return await ctx.db
            .query("phoneConfigs")
            .filter((q) => q.eq(q.field("isActive"), true))
            .collect();
    },
});
