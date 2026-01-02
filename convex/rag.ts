/**
 * RAG (Retrieval-Augmented Generation) Service
 * 
 * Uses @convex-dev/rag for low-latency semantic search during voice calls.
 * Documents are ingested with automatic chunking and embedding.
 * 
 * SIMPLIFIED: No filters - relies purely on semantic search for domain-agnostic retrieval.
 * Categories and metadata are embedded in chunk text for semantic matching.
 */

import { RAG } from "@convex-dev/rag";
import { openai } from "@ai-sdk/openai";
import { components } from "./_generated/api";
import { action } from "./_generated/server";
import { v } from "convex/values";

// Initialize RAG with OpenAI embeddings - NO FILTERS
// Pure semantic search - embeddings capture meaning without filter complexity
export const rag = new RAG(components.rag, {
    textEmbeddingModel: openai.embedding("text-embedding-3-small"),
    embeddingDimension: 1536,
    // No filterNames - semantic search handles all retrieval
});

/**
 * Ingest content (text or chunks) into the knowledge base
 * Called during document upload (not time-sensitive)
 * Categories/metadata should be embedded in chunk text for semantic search
 */
export const ingest = action({
    args: {
        namespace: v.string(),      // Organization ID
        key: v.optional(v.string()), // Unique document key for updates
        text: v.optional(v.string()), // Full document text
        chunks: v.optional(v.array(v.string())), // Pre-calculated chunks
        title: v.optional(v.string()),
    },
    handler: async (ctx, args) => {
        if (!args.text && !args.chunks) {
            throw new Error("Must provide either text or chunks");
        }

        const commonArgs = {
            namespace: args.namespace,
            key: args.key,
            title: args.title,
            // No filterValues - pure semantic search
        };

        let result;
        if (args.text) {
            result = await rag.add(ctx, { ...commonArgs, text: args.text });
        } else {
            result = await rag.add(ctx, { ...commonArgs, chunks: args.chunks! });
        }

        return {
            entryId: result.entryId,
            status: result.status,
        };
    },
});

/**
 * Search knowledge base - optimized for voice agent latency
 * Single action: embedding + vector search in one call
 * Pure semantic search - no filters, relies on embedding similarity
 */
export const search = action({
    args: {
        namespace: v.string(),      // Organization ID
        query: v.string(),          // User's question
        limit: v.optional(v.number()),
        minScore: v.optional(v.number()),
    },
    handler: async (ctx, args) => {
        const { results, text, entries, usage } = await rag.search(ctx, {
            namespace: args.namespace,
            query: args.query,
            limit: args.limit ?? 5,
            vectorScoreThreshold: args.minScore ?? 0.3,
            // No filters - pure semantic search
            chunkContext: { before: 1, after: 1 }, // Include surrounding chunks
        });

        console.log("RAG Search Results:", JSON.stringify(results[0] || "No results", null, 2));

        return {
            text,  // Formatted text for LLM prompt
            results: results.map(r => {
                const entry = entries.find(e => e.entryId === r.entryId);
                return {
                    score: r.score,
                    text: entry?.text,
                    entryId: r.entryId,
                };
            }),
            resultsCount: results.length,
            entries: entries.map(e => ({
                entryId: e.entryId,
                title: e.title,
                text: e.text,
            })),
            tokensUsed: usage.tokens,
        };
    },
});

/**
 * Delete a document from knowledge base
 */
export const deleteDocument = action({
    args: {
        entryId: v.string(),
    },
    handler: async (ctx, args) => {
        await rag.delete(ctx, { entryId: args.entryId as any });
        return { success: true };
    },
});

/**
 * Clear all entries in a namespace - uses search to find entries
 */
export const clearNamespace = action({
    args: {
        namespace: v.string(),
    },
    handler: async (ctx, args) => {
        let deleted = 0;
        let attempts = 0;
        const maxAttempts = 20;  // Safety limit
        
        console.log(`Starting to clear namespace: ${args.namespace}`);
        
        // Use various broad queries to find and delete entries
        const queries = ["the", "a", "is", "item", "price", "menu", "food", "all"];
        
        while (attempts < maxAttempts) {
            attempts++;
            let foundAny = false;
            
            for (const query of queries) {
                try {
                    const searchResult = await rag.search(ctx, {
                        namespace: args.namespace,
                        query: query,
                        limit: 50,
                        vectorScoreThreshold: 0,
                    });
                    
                    if (searchResult.results.length > 0) {
                        foundAny = true;
                        console.log(`Found ${searchResult.results.length} entries with query "${query}"`);
                        
                        for (const result of searchResult.results) {
                            try {
                                await rag.delete(ctx, { entryId: result.entryId as any });
                                deleted++;
                            } catch (e) {
                                // Entry may already be deleted
                            }
                        }
                    }
                } catch (e) {
                    console.log(`Search error for "${query}":`, e);
                }
            }
            
            if (!foundAny) {
                console.log(`No more entries found after ${attempts} attempts`);
                break;
            }
        }
        
        console.log(`Deleted ${deleted} total entries from namespace ${args.namespace}`);
        return { deleted };
    },
});

/**
 * List entries in a namespace
 */
export const listEntries = action({
    args: {
        namespace: v.string(),
        status: v.optional(v.union(v.literal("ready"), v.literal("pending"), v.literal("replaced"))),
        limit: v.optional(v.number()),
    },
    handler: async (ctx, args) => {
        // Note: RAG list uses namespaceId syntax
        const namespaceId = args.namespace as any; // Cast to NamespaceId type
        const result = await rag.list(ctx, {
            namespaceId,
            status: args.status,
            paginationOpts: { cursor: null, numItems: args.limit ?? 100 },
        });

        return {
            entries: result.page.map(e => ({
                entryId: e.entryId,
                key: e.key,
                title: e.title,
                status: e.status,
            })),
            hasMore: !result.isDone,
        };
    },
});
