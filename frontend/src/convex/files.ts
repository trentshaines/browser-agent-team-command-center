import { v } from "convex/values";
import { query, mutation } from "./_generated/server";

export const list = query({
  args: {},
  handler: async (ctx) => {
    const files = await ctx.db.query("files").collect();
    return await Promise.all(
      files.map(async (f) => ({
        ...f,
        url: await ctx.storage.getUrl(f.storageId),
      }))
    );
  },
});

export const generateUploadUrl = mutation({
  args: {},
  handler: async (ctx) => {
    return await ctx.storage.generateUploadUrl();
  },
});

export const save = mutation({
  args: {
    storageId: v.id("_storage"),
    name: v.string(),
    size: v.number(),
    type: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("files", {
      storageId: args.storageId,
      name: args.name,
      size: args.size,
      type: args.type,
    });
  },
});

export const remove = mutation({
  args: { id: v.id("files") },
  handler: async (ctx, { id }) => {
    const file = await ctx.db.get(id);
    if (file) {
      await ctx.storage.delete(file.storageId);
      await ctx.db.delete(id);
    }
  },
});
