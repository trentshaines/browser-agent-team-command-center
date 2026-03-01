import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  sessions: defineTable({
    clientId: v.string(),
    title: v.string(),
    updatedAt: v.number(),
  })
    .index("by_clientId", ["clientId"])
    .index("by_updatedAt", ["updatedAt"]),

  messages: defineTable({
    sessionId: v.id("sessions"),
    clientId: v.string(),
    role: v.string(),
    content: v.string(),
    category: v.optional(v.string()),
    senderName: v.optional(v.string()),
    agentId: v.optional(v.string()),
  }).index("by_sessionId", ["sessionId"]),

  agentRuns: defineTable({
    sessionId: v.id("sessions"),
    clientId: v.string(),
    name: v.optional(v.string()),
    task: v.string(),
    status: v.string(),
    result: v.optional(v.string()),
    totalSteps: v.optional(v.number()),
    liveUrl: v.optional(v.string()),
  })
    .index("by_sessionId", ["sessionId"])
    .index("by_clientId", ["clientId"]),

  agentSteps: defineTable({
    agentRunId: v.id("agentRuns"),
    step: v.number(),
    url: v.optional(v.string()),
    action: v.optional(v.string()),
    thought: v.optional(v.string()),
    evaluation: v.optional(v.string()),
    success: v.optional(v.boolean()),
    extractedContent: v.optional(v.string()),
    error: v.optional(v.string()),
  })
    .index("by_agentRunId", ["agentRunId"])
    .index("by_agentRunId_step", ["agentRunId", "step"]),

  files: defineTable({
    storageId: v.id("_storage"),
    name: v.string(),
    size: v.number(),
    type: v.string(),
  }),
});
