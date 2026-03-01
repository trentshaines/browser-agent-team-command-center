import { v } from "convex/values";
import { query, mutation } from "./_generated/server";

export const listBySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_sessionId", (q) => q.eq("sessionId", sessionId))
      .collect();
  },
});

export const send = mutation({
  args: {
    sessionId: v.id("sessions"),
    clientId: v.string(),
    role: v.string(),
    content: v.string(),
    category: v.optional(v.string()),
    senderName: v.optional(v.string()),
    agentId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("messages", args);
  },
});

export const updateContent = mutation({
  args: { id: v.id("messages"), content: v.string() },
  handler: async (ctx, { id, content }) => {
    await ctx.db.patch(id, { content });
  },
});
