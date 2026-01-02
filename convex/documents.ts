import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

/**
 * Create a new document record
 */
export const create = mutation({
    args: {
        organizationId: v.string(),
        documentId: v.string(),
        fileName: v.string(),
        fileType: v.string(),
        fileSize: v.number(),
        sourceType: v.string(),
        status: v.union(
            v.literal("uploading"),
            v.literal("processing"),
            v.literal("completed"),
            v.literal("failed")
        ),
        chunkCount: v.number(),
        metadata: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const id = await ctx.db.insert("documents", {
            organizationId: args.organizationId,
            documentId: args.documentId,
            fileName: args.fileName,
            fileType: args.fileType,
            fileSize: args.fileSize,
            sourceType: args.sourceType,
            status: args.status,
            chunkCount: args.chunkCount,
            metadata: args.metadata,
            uploadedAt: Date.now(),
        });
        return id;
    },
});

/**
 * Update document status
 */
export const updateStatus = mutation({
    args: {
        documentId: v.string(),
        status: v.union(
            v.literal("uploading"),
            v.literal("processing"),
            v.literal("completed"),
            v.literal("failed")
        ),
        chunkCount: v.optional(v.number()),
        ragEntryIds: v.optional(v.array(v.string())),
        errorMessage: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        const doc = await ctx.db
            .query("documents")
            .withIndex("by_document_id", (q) => q.eq("documentId", args.documentId))
            .unique();

        if (!doc) {
            throw new Error(`Document not found: ${args.documentId}`);
        }

        const updates: any = {
            status: args.status,
            processedAt: Date.now(),
        };

        if (args.chunkCount !== undefined) {
            updates.chunkCount = args.chunkCount;
        }

        if (args.ragEntryIds !== undefined) {
            updates.ragEntryIds = args.ragEntryIds;
        }

        if (args.errorMessage !== undefined) {
            updates.errorMessage = args.errorMessage;
        }

        await ctx.db.patch(doc._id, updates);
        return doc._id;
    },
});

/**
 * Get document by ID
 */
export const getByDocumentId = query({
    args: { documentId: v.string() },
    handler: async (ctx, args) => {
        return await ctx.db
            .query("documents")
            .withIndex("by_document_id", (q) => q.eq("documentId", args.documentId))
            .unique();
    },
});

/**
 * List documents for an organization
 */
export const listByOrganization = query({
    args: {
        organizationId: v.string(),
        status: v.optional(v.union(
            v.literal("uploading"),
            v.literal("processing"),
            v.literal("completed"),
            v.literal("failed")
        )),
    },
    handler: async (ctx, args) => {
        let query = ctx.db
            .query("documents")
            .withIndex("by_organization_id", (q) => q.eq("organizationId", args.organizationId));

        const docs = await query.collect();

        // Filter by status if provided
        if (args.status) {
            return docs.filter((doc) => doc.status === args.status);
        }

        return docs;
    },
});

/**
 * Delete document by ID
 */
export const deleteByDocumentId = mutation({
    args: { documentId: v.string() },
    handler: async (ctx, args) => {
        const doc = await ctx.db
            .query("documents")
            .withIndex("by_document_id", (q) => q.eq("documentId", args.documentId))
            .unique();

        if (doc) {
            await ctx.db.delete(doc._id);
            return { deleted: true };
        }

        return { deleted: false };
    },
});

/**
 * Get document count for an organization
 */
export const getCount = query({
    args: { organizationId: v.string() },
    handler: async (ctx, args) => {
        const docs = await ctx.db
            .query("documents")
            .withIndex("by_organization_id", (q) => q.eq("organizationId", args.organizationId))
            .collect();

        return docs.length;
    },
});

/**
 * Clear all documents from the database
 */
export const clearAllDocuments = mutation({
    args: {},
    handler: async (ctx) => {
        const docs = await ctx.db.query("documents").collect();
        let deleted = 0;
        for (const doc of docs) {
            await ctx.db.delete(doc._id);
            deleted++;
        }
        return { deleted };
    },
});
