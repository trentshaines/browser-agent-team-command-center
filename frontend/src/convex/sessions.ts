import { v } from "convex/values";
import { query, mutation } from "./_generated/server";

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("sessions")
      .withIndex("by_updatedAt")
      .order("desc")
      .collect();
  },
});

export const getByClientId = query({
  args: { clientId: v.string() },
  handler: async (ctx, { clientId }) => {
    return await ctx.db
      .query("sessions")
      .withIndex("by_clientId", (q) => q.eq("clientId", clientId))
      .unique();
  },
});

export const create = mutation({
  args: { clientId: v.string(), title: v.string() },
  handler: async (ctx, { clientId, title }) => {
    return await ctx.db.insert("sessions", {
      clientId,
      title,
      updatedAt: Date.now(),
    });
  },
});

export const updateTitle = mutation({
  args: { id: v.id("sessions"), title: v.string() },
  handler: async (ctx, { id, title }) => {
    await ctx.db.patch(id, { title });
  },
});

export const bumpUpdated = mutation({
  args: { id: v.id("sessions") },
  handler: async (ctx, { id }) => {
    await ctx.db.patch(id, { updatedAt: Date.now() });
  },
});

export const remove = mutation({
  args: { id: v.id("sessions") },
  handler: async (ctx, { id }) => {
    // Cascade: delete messages
    const messages = await ctx.db
      .query("messages")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", id))
      .collect();
    for (const m of messages) {
      await ctx.db.delete(m._id);
    }

    // Cascade: delete agent runs and their steps
    const runs = await ctx.db
      .query("agentRuns")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", id))
      .collect();
    for (const run of runs) {
      const steps = await ctx.db
        .query("agentSteps")
        .withIndex("by_agentRunId", (q) => q.eq("agentRunId", run._id))
        .collect();
      for (const step of steps) {
        await ctx.db.delete(step._id);
      }
      await ctx.db.delete(run._id);
    }

    await ctx.db.delete(id);
  },
});
