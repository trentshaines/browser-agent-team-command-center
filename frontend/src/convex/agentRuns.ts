import { v } from "convex/values";
import { query, mutation } from "./_generated/server";

export const listBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    const runs = await ctx.db
      .query("agentRuns")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", sessionId))
      .collect();

    // Join steps for each run
    return await Promise.all(
      runs.map(async (run) => {
        const steps = await ctx.db
          .query("agentSteps")
          .withIndex("by_agentRunId", (q) => q.eq("agentRunId", run._id))
          .collect();
        // Sort steps by step number
        steps.sort((a, b) => a.step - b.step);
        return { ...run, steps };
      })
    );
  },
});

export const getByClientId = query({
  args: { clientId: v.string() },
  handler: async (ctx, { clientId }) => {
    return await ctx.db
      .query("agentRuns")
      .withIndex("by_clientId", (q) => q.eq("clientId", clientId))
      .unique();
  },
});

export const create = mutation({
  args: {
    sessionId: v.id("sessions"),
    clientId: v.string(),
    name: v.optional(v.string()),
    task: v.string(),
    status: v.string(),
    liveUrl: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("agentRuns", args);
  },
});

export const updateStatus = mutation({
  args: {
    id: v.id("agentRuns"),
    status: v.string(),
    result: v.optional(v.string()),
    totalSteps: v.optional(v.number()),
  },
  handler: async (ctx, { id, status, result, totalSteps }) => {
    const patch: Record<string, unknown> = { status };
    if (result !== undefined) patch.result = result;
    if (totalSteps !== undefined) patch.totalSteps = totalSteps;
    await ctx.db.patch(id, patch);
  },
});

export const addStep = mutation({
  args: {
    agentRunId: v.id("agentRuns"),
    step: v.number(),
    url: v.optional(v.string()),
    action: v.optional(v.string()),
    thought: v.optional(v.string()),
    evaluation: v.optional(v.string()),
    success: v.optional(v.boolean()),
    extractedContent: v.optional(v.string()),
    error: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    // Deduplicate by step number
    const existing = await ctx.db
      .query("agentSteps")
      .withIndex("by_agentRunId_step", (q) =>
        q.eq("agentRunId", args.agentRunId).eq("step", args.step)
      )
      .unique();
    if (existing) return existing._id;
    return await ctx.db.insert("agentSteps", args);
  },
});
