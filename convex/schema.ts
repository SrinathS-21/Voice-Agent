import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
    // ============================================
    // VOICE AGENT TABLES
    // ============================================

    // Organizations (multi-tenant support)
    organizations: defineTable({
        slug: v.string(),
        name: v.string(),
        billingCustomerId: v.optional(v.string()),
        status: v.union(v.literal("active"), v.literal("inactive")),
        config: v.optional(v.string()), // JSON string for custom config
        createdAt: v.number(),
    })
        .index("by_slug", ["slug"]),

    // Phone number configurations
    phoneConfigs: defineTable({
        phoneNumber: v.string(),
        organizationId: v.string(),
        jobType: v.string(), // restaurant/pharmacy/hotel
        configJson: v.string(), // VoiceAgentConfigSchema as JSON
        agentId: v.optional(v.string()),
        isActive: v.boolean(),
        createdAt: v.number(),
        updatedAt: v.number(),
    })
        .index("by_phone_number", ["phoneNumber"])
        .index("by_organization_id", ["organizationId"]),

    // Call sessions - tracks active and completed calls
    callSessions: defineTable({
        sessionId: v.string(),
        organizationId: v.string(),
        callSid: v.optional(v.string()), // Twilio call SID
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
        config: v.optional(v.string()), // JSON of call config
        createdAt: v.number(),
        updatedAt: v.number(),
    })
        .index("by_session_id", ["sessionId"])
        .index("by_call_sid", ["callSid"])
        .index("by_organization_id", ["organizationId"])
        .index("by_status", ["status"])
        .index("by_status_and_organization", ["status", "organizationId"]),

    // Call interactions - individual messages and function calls
    callInteractions: defineTable({
        sessionId: v.string(),
        interactionType: v.union(
            v.literal("user_message"),
            v.literal("agent_response"),
            v.literal("function_call")
        ),
        timestamp: v.number(),
        userInput: v.optional(v.string()),
        agentResponse: v.optional(v.string()),
        functionName: v.optional(v.string()),
        functionParams: v.optional(v.string()), // JSON
        functionResult: v.optional(v.string()), // JSON
        sentiment: v.optional(v.union(
            v.literal("positive"),
            v.literal("negative"),
            v.literal("neutral")
        )),
    })
        .index("by_session_id", ["sessionId"])
        .index("by_timestamp", ["timestamp"]),

    // Call metrics - performance tracking
    callMetrics: defineTable({
        sessionId: v.string(),
        organizationId: v.string(),
        latencyMs: v.optional(v.number()),
        audioQualityScore: v.optional(v.number()),
        callCompleted: v.boolean(),
        errorsCount: v.number(),
        functionsCalledCount: v.number(),
        userSatisfied: v.optional(v.boolean()),
        deepgramUsageSeconds: v.optional(v.number()),
        createdAt: v.number(),
    })
        .index("by_session_id", ["sessionId"])
        .index("by_organization_id", ["organizationId"]),

    // Persistent agents (reusable configurations)
    agents: defineTable({
        organizationId: v.string(),
        name: v.string(),
        role: v.optional(v.string()),
        systemPrompt: v.string(),
        config: v.optional(v.string()), // JSON
        createdAt: v.number(),
        updatedAt: v.number(),
    })
        .index("by_organization_id", ["organizationId"]),



    // ============================================
    // KNOWLEDGE BASE TABLES
    // ============================================

    // Documents - tracks uploaded files
    documents: defineTable({
        organizationId: v.string(),
        documentId: v.string(), // Unique ID for this document
        fileName: v.string(),
        fileType: v.string(), // "pdf", "csv", "xlsx", "docx", "image", etc.
        fileSize: v.number(), // bytes
        sourceType: v.string(), // "menu", "faq", "policy", "catalog", etc.
        status: v.union(
            v.literal("uploading"),
            v.literal("processing"),
            v.literal("completed"),
            v.literal("failed")
        ),
        chunkCount: v.number(), // Total chunks generated
        ragEntryIds: v.optional(v.array(v.string())), // IDs of RAG entries for this document
        metadata: v.optional(v.string()), // JSON: custom metadata
        errorMessage: v.optional(v.string()),
        uploadedAt: v.number(),
        processedAt: v.optional(v.number()),
    })
        .index("by_organization_id", ["organizationId"])
        .index("by_document_id", ["documentId"])
        .index("by_status", ["organizationId", "status"]),

    // Function schemas - dynamic function definitions
    functionSchemas: defineTable({
        organizationId: v.string(),
        domain: v.string(), // "restaurant", "pharmacy", "hotel", "retail"
        functionName: v.string(),
        description: v.string(),
        parameters: v.string(), // JSON schema
        handlerType: v.union(
            v.literal("vector_search"),
            v.literal("convex_query"),
            v.literal("webhook"),
            v.literal("static")
        ),
        handlerConfig: v.string(), // JSON: handler-specific configuration
        isActive: v.boolean(),
        createdAt: v.number(),
        updatedAt: v.number(),
    })
        .index("by_organization_id", ["organizationId"])
        .index("by_function_name", ["organizationId", "functionName"])
        .index("by_domain", ["domain"]),

    // ============================================
    // USER MANAGEMENT
    // ============================================

    // Users (multi-tenant user management)
    users: defineTable({
        name: v.string(),
        email: v.string(),
        authId: v.string(),
        organizationId: v.string(),
    })
        .index("by_organization_id", ["organizationId"])
        .index("by_auth_id", ["authId"]),
});
