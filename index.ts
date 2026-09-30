import { Bot, Context, InlineKeyboard, webhookCallback } from "grammy";

export interface Env {
  TELEGRAM_TOKEN: string;
  ADMIN_CHAT_ID: string;
  ADMIN_THREAD_ID?: string;  // <-- Добавили
  OWNER_ID: string;
  DB: D1Database;
}

export interface MyContext extends Context {
  env: Env;
}

// --- Вспомогательные функции ---

function getUserLink(user: any): string {
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim() || "User";
  return `<a href="tg://user?id=${user.id}">${name}</a>`;
}

async function logAction(ctx: MyContext, action: string, info: string) {
  try {
    if (!ctx.env.ADMIN_CHAT_ID || !ctx.from) return;
    const userLink = getUserLink(ctx.from);
    const chatInfo = ctx.chat?.title ? `Chat: ${ctx.chat.title}` : `Chat ID: ${ctx.chat?.id}`;
    const msg = `${userLink}\nAction: ${action}\nInfo: ${info}\n${chatInfo}`;
    
    await ctx.api.sendMessage(ctx.env.ADMIN_CHAT_ID, msg, { parse_mode: "HTML" });
  } catch (err) {
    console.error("Log error (ignored):", err);
  }
}

async function hasPermission(ctx: MyContext): Promise<boolean> {
  if (!ctx.from) return false;
  const userId = ctx.from.id;
  if (userId.toString() === ctx.env.OWNER_ID) return true;
  
  const botAdmin = await ctx.env.DB.prepare(
    "SELECT user_id FROM bot_admins WHERE user_id = ?"
  ).bind(userId).first();
  if (botAdmin) return true;
  
  if (ctx.chat?.type === "private") return true;
  
  try {
    const member = await ctx.api.getChatMember(ctx.chat.id, userId);
    return member.status === "administrator" || member.status === "creator";
  } catch {
    return false;
  }
}

function getKeyboard(isClosed: boolean, hasKeepers: boolean): InlineKeyboard {
  const kb = new InlineKeyboard();
  kb.row(isClosed ? { text: "Open event", callback_data: "change_state" } : { text: "Close event", callback_data: "change_state" });

  if (!isClosed) {
    kb.row(
      { text: "✅ Going", callback_data: "Go" },
      { text: "❌ Not going", callback_data: "Not_go" },
      { text: "💭 Not sure", callback_data: "Not_sure" }
    );
    kb.row(
      { text: "➕ Add", callback_data: "Add" },
      { text: "➖ Sub", callback_data: "Sub" },
      { text: "➖ Sub all", callback_data: "Sub_all" }
    );
    if (hasKeepers) {
      kb.row(
        { text: "✅🥅 Going", callback_data: "Go_keeper" },
        { text: "➕🥅 Add", callback_data: "Add_keeper" },
        { text: "➖🥅 Sub", callback_data: "Sub_keeper" }
      );
    }
  } else {
    kb.row({ text: "❌ Not going", callback_data: "Not_go" });
    kb.row(
      { text: "➖ Sub", callback_data: "Sub" },
      { text: "➖ Sub all", callback_data: "Sub_all" }
    );
    if (hasKeepers) {
      kb.row({ text: "➖🥅 Sub", callback_data: "Sub_keeper" });
    }
  }
  return kb;
}

async function buildEventText(
  db: D1Database,
  chatId: number,
  messageId: number,
  eventName: string,
  isClosed: boolean,
  hasKeepers: boolean
): Promise<string> {
  const { results } = await db.prepare(
    "SELECT user_id, user_name, status, plus_count, keeper_plus_count FROM participants WHERE chat_id = ? AND message_id = ?"
  ).bind(chatId, messageId).all();

  const participants = (results || []) as any[];

  const going = participants.filter((p: any) => p.status === 'going');
  const keeper = participants.filter((p: any) => p.status === 'keeper');
  const notGoing = participants.filter((p: any) => p.status === 'not_going');
  const notSure = participants.filter((p: any) => p.status === 'not_sure');

  const goingCount = going.length;
  const keeperCount = keeper.length;
  // Плюсы считаем по ВСЕМ участникам: они живут независимо от статуса (как в оригинале)
  const goingPlus = participants.reduce((s: number, p: any) => s + (p.plus_count || 0), 0);
  const keeperPlus = participants.reduce((s: number, p: any) => s + (p.keeper_plus_count || 0), 0);
  const totalGoing = goingCount + keeperCount + goingPlus + keeperPlus;

  let lines: string[] = [];
  if (isClosed) lines.push("❌ EVENT CLOSED ❌");
  lines.push(eventName);

  if (hasKeepers) {
    lines.push("Going😀🥅:");
    const keeperLines: string[] = [];
    keeper.forEach((p: any) => keeperLines.push(`✅ ${p.user_name}`));
    participants.forEach((p: any) => {
      if ((p.keeper_plus_count || 0) > 0) keeperLines.push(`➕🥅${p.keeper_plus_count}, from: ${p.user_name}`);
    });
    lines.push(...(keeperLines.length ? keeperLines : ["-"]));
  }

  lines.push("Going😀:");
  const goingLines: string[] = [];
  going.forEach((p: any) => goingLines.push(`✅ ${p.user_name}`));
  participants.forEach((p: any) => {
    if ((p.plus_count || 0) > 0) goingLines.push(`➕${p.plus_count}, from: ${p.user_name}`);
  });
  lines.push(...(goingLines.length ? goingLines : ["-"]));

  lines.push("Not going😐:");
  lines.push(...(notGoing.length ? notGoing.map((p: any) => `❌ ${p.user_name}`) : ["-"]));

  lines.push("Not sure🤔:");
  lines.push(...(notSure.length ? notSure.map((p: any) => `💭 ${p.user_name}`) : ["-"]));

  lines.push(`Total going: ${totalGoing}`);
  lines.push(`✅: ${goingCount + keeperCount}`);
  lines.push(`➕: ${goingPlus + keeperPlus}`);
  lines.push(`❌: ${notGoing.length}`);
  lines.push(`💭: ${notSure.length}`);

  return lines.join("\n");
}

async function createEvent(ctx: MyContext, hasKeepers: boolean) {
  if (!ctx.message) return;
  const args = ctx.message.text?.split(" ").slice(1) || [];
  const eventName = args.length > 0 ? `👉 ${args.join(" ")} 👈` : "👉 No name event 👈";

  const sentMsg = await ctx.reply("Создаю опрос...", { parse_mode: "HTML" });
  const messageId = sentMsg.message_id;
  const chatId = ctx.chat.id;

  await ctx.env.DB.prepare(
    "INSERT INTO events (chat_id, message_id, event_name, has_keepers, is_closed) VALUES (?, ?, ?, ?, 0)"
  ).bind(chatId, messageId, eventName, hasKeepers ? 1 : 0).run();

  const finalText = await buildEventText(ctx.env.DB, chatId, messageId, eventName, false, hasKeepers);
  const keyboard = getKeyboard(false, hasKeepers);

  await ctx.api.editMessageText(chatId, messageId, finalText, { 
    reply_markup: keyboard, 
    parse_mode: "HTML" 
  });
  await logAction(ctx, "CREATE_EVENT", `Event: ${eventName}, Keepers: ${hasKeepers}`);
}

// --- Функция настройки команд ---
function setupBot(bot: Bot<MyContext>, env: any) {
  bot.use(async (ctx, next) => {
    ctx.env = env as Env; // <-- Приводим к нашему типу
    await next();
  });

  bot.command("event", (ctx) => createEvent(ctx, false));
  bot.command("eventk", (ctx) => createEvent(ctx, true));

  bot.command("start", async (ctx) => {
    await logAction(ctx, "START", `Chat: ${ctx.chat?.id || 'unknown'}`);
    await ctx.reply(
      "I'm a bot to organize events.\n\n" +
      "Commands:\n" +
      "/event <name> — standard event\n" +
      "/eventk <name> — event with keepers (🥅)\n" +
      "/description — detailed description\n\n" +
      "Admin commands:\n" +
      "/addadmin <user_id>\n" +
      "/removeadmin <user_id>\n" +
      "/admins"
    );
  });

  bot.command("description", async (ctx) => {
    let desc = "Для создания опроса введите команду '/event' или '/eventk', указав название.\n" +
               "Кнопки ✅/❌/💭 управляют вашим статусом.\n" +
               "Кнопки ➕/➖ управляют количеством людей.\n" +
               "Кнопка ➖ Sub all убирает все ваши плюсы.\n\n" +
               "🥅 В режиме /eventk:\n" +
               "Кнопка ✅🥅 Going добавит вас как вратаря.\n" +
               "Кнопки ➕🥅 и ➖🥅 управляют плюсами вратаря.\n" +
               "Sub all НЕ удаляет плюсы вратарей.";
    await ctx.reply(desc);
  });

  bot.command("addadmin", async (ctx) => {
    if (!ctx.from || !ctx.message) return;
    if (ctx.from.id.toString() !== ctx.env.OWNER_ID) {
      await ctx.reply("⛔ Только создатель бота может добавлять администраторов."); return;
    }
    const args = ctx.message.text?.split(" ");
    if (!args || args.length < 2) { await ctx.reply("Использование: /addadmin <user_id>"); return; }
    const targetUserId = parseInt(args[1]);
    if (isNaN(targetUserId)) { await ctx.reply("❌ Неверный user_id."); return; }
    const existing = await ctx.env.DB.prepare("SELECT user_id FROM bot_admins WHERE user_id = ?").bind(targetUserId).first();
    if (existing) { await ctx.reply(`ℹ️ Пользователь ${targetUserId} уже админ.`); return; }
    await ctx.env.DB.prepare("INSERT INTO bot_admins (user_id, added_by) VALUES (?, ?)").bind(targetUserId, ctx.from.id).run();
    await ctx.reply(`✅ Пользователь ${targetUserId} добавлен.`);
    await logAction(ctx, "ADD_ADMIN", `Added user ${targetUserId}`);
  });

  bot.command("removeadmin", async (ctx) => {
    if (!ctx.from || !ctx.message) return;
    if (ctx.from.id.toString() !== ctx.env.OWNER_ID) {
      await ctx.reply("⛔ Только создатель бота может удалять администраторов."); return;
    }
    const args = ctx.message.text?.split(" ");
    if (!args || args.length < 2) { await ctx.reply("Использование: /removeadmin <user_id>"); return; }
    const targetUserId = parseInt(args[1]);
    if (isNaN(targetUserId)) { await ctx.reply("❌ Неверный user_id."); return; }
    const result = await ctx.env.DB.prepare("DELETE FROM bot_admins WHERE user_id = ?").bind(targetUserId).run();
    if (result.meta.changes > 0) { await ctx.reply(`✅ Пользователь ${targetUserId} удален.`); }
    else { await ctx.reply(`ℹ️ Пользователь ${targetUserId} не найден.`); }
  });

  bot.command("admins", async (ctx) => {
    if (!ctx.from) return;
    const isOwner = ctx.from.id.toString() === ctx.env.OWNER_ID;
    const isBotAdmin = await ctx.env.DB.prepare("SELECT user_id FROM bot_admins WHERE user_id = ?").bind(ctx.from.id).first();
    if (!isOwner && !isBotAdmin) { await ctx.reply("⛔ У вас нет прав."); return; }
    const { results } = await ctx.env.DB.prepare("SELECT user_id, added_at FROM bot_admins ORDER BY added_at DESC").all();
    const admins = (results || []) as any[];
    let msg = "👥 Администраторы бота:\n\n";
    msg += `👑 Создатель: ${ctx.env.OWNER_ID}\n\n`;
    if (admins.length === 0) msg += "(список пуст)";
    else admins.forEach((admin, index) => { msg += `${index + 1}. ID: ${admin.user_id}\n   Добавлен: ${admin.added_at}\n\n`; });
    await ctx.reply(msg);
  });

  bot.command("rename", async (ctx) => {
    if (!ctx.message) return;

    const args = ctx.message.text?.split(" ").slice(1) || [];
    if (args.length === 0) {
      await ctx.reply("Использование: ответь на сообщение события командой:\n/rename Новое название");
      return;
    }

    const target = ctx.message.reply_to_message;
    if (!target) {
      await ctx.reply("⚠️ Ответь на сообщение события, которое нужно переименовать.");
      return;
    }

    if (!await hasPermission(ctx)) {
      await ctx.reply("⛔ Нет прав: переименовывать могут создатель бота, админы бота и админы чата.");
      return;
    }

    const msgId = target.message_id;
    const chatId = ctx.chat.id;
    const newName = `👉 ${args.join(" ")} 👈`;

    const event = await ctx.env.DB.prepare(
      "SELECT event_name, has_keepers, is_closed FROM events WHERE chat_id = ? AND message_id = ?"
    ).bind(chatId, msgId).first() as any;

    if (!event) {
      await ctx.reply("⚠️ Это сообщение не является событием из базы данных.");
      return;
    }

    await ctx.env.DB.prepare(
      "UPDATE events SET event_name = ? WHERE chat_id = ? AND message_id = ?"
    ).bind(newName, chatId, msgId).run();

    const newText = await buildEventText(
      ctx.env.DB, chatId, msgId, newName,
      event.is_closed === 1, event.has_keepers === 1
    );

    await ctx.api.editMessageText(chatId, msgId, newText, {
      reply_markup: getKeyboard(event.is_closed === 1, event.has_keepers === 1),
      parse_mode: "HTML"
    });

    await ctx.reply("✅ Событие переименовано.");
    await logAction(ctx, "RENAME_EVENT", `Message ID: ${msgId}, New name: ${newName}`);
  });

  bot.callbackQuery("change_state", async (ctx) => {
    console.log("🔒 CHANGE_STATE pressed by:", ctx.from?.id);

    if (!ctx.callbackQuery || !ctx.from) {
      console.log("❌ change_state: missing callbackQuery or from");
      await ctx.answerCallbackQuery("Error").catch(() => {});
      return;
    }

    try {
      // ✅ Ключевое исправление: берём сообщение из callbackQuery
      const callbackMessage = ctx.callbackQuery.message;
      if (!callbackMessage || !('message_id' in callbackMessage)) {
        console.log("❌ change_state: message inaccessible");
        await ctx.answerCallbackQuery("⚠️ Cannot access this message").catch(() => {});
        return;
      }

      const msgId = callbackMessage.message_id;
      const chatId = callbackMessage.chat.id;

      if (!await hasPermission(ctx)) {
        console.log("⛔ change_state: no permission for user", ctx.from.id);
        await ctx.answerCallbackQuery("⛔ You have no permission to open or close event");
        return;
      }

      const event = await ctx.env.DB.prepare(
        "SELECT event_name, has_keepers, is_closed FROM events WHERE chat_id = ? AND message_id = ?"
      ).bind(chatId, msgId).first() as any;

      if (!event) {
        console.log("❌ change_state: event not found, message_id:", msgId);
        await ctx.answerCallbackQuery("⚠️ Событие не найдено в БД").catch(() => {});
        return;
      }

      const newIsClosed = event.is_closed === 1 ? 0 : 1;
      await ctx.env.DB.prepare(
        "UPDATE events SET is_closed = ? WHERE chat_id = ? AND message_id = ?"
      ).bind(newIsClosed, chatId, msgId).run();

      const newText = await buildEventText(
        ctx.env.DB, chatId, msgId, event.event_name,
        newIsClosed === 1, event.has_keepers === 1
      );

      await ctx.editMessageText(newText, {
        reply_markup: getKeyboard(newIsClosed === 1, event.has_keepers === 1),
        parse_mode: "HTML"
      });

      await ctx.answerCallbackQuery(newIsClosed === 1 ? "You closed event" : "You opened event");
      await logAction(ctx, "CHANGE_STATE", `Message ID: ${msgId}, Closed: ${newIsClosed}`);
      console.log("✨ change_state OK, new is_closed:", newIsClosed);
    } catch (err) {
      console.error("❌ change_state error:", err);
      await ctx.answerCallbackQuery("Error: " + (err as Error).message).catch(() => {});
    }
  });

  const actions = ["Go", "Not_go", "Not_sure", "Add", "Sub", "Sub_all", "Go_keeper", "Add_keeper", "Sub_keeper"];
  bot.callbackQuery(actions, async (ctx) => {
    console.log("🔥 CALLBACK RECEIVED:", ctx.callbackQuery?.data, "from user:", ctx.from?.id);
    
    if (!ctx.callbackQuery || !ctx.from) {
      console.log("❌ Missing callbackQuery or from");
      await ctx.answerCallbackQuery("Error").catch(() => {});
      return;
    }
    
    try {
      // ✅ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: берём сообщение из callbackQuery
      const callbackMessage = ctx.callbackQuery.message;
      
      // Проверяем, что сообщение доступно (иногда Telegram делает его "InaccessibleMessage")
      if (!callbackMessage || !('message_id' in callbackMessage)) {
        console.log("❌ Message is inaccessible or missing");
        await ctx.answerCallbackQuery("⚠️ Cannot access this message").catch(() => {});
        return;
      }
      
      const action = ctx.callbackQuery.data;
      const msgId = callbackMessage.message_id;
      const chatId = callbackMessage.chat.id;
      const userId = ctx.from.id;
      const userLink = getUserLink(ctx.from);
      
      console.log("🔎 Looking for event in DB, message_id:", msgId);
      
      const event = await ctx.env.DB.prepare(
        "SELECT event_name, has_keepers, is_closed FROM events WHERE chat_id = ? AND message_id = ?"
      ).bind(chatId, msgId).first() as any;
      
      if (!event) {
        console.log("❌ Event not found in DB for message_id:", msgId);
        await ctx.answerCallbackQuery("⚠️ Событие не найдено в БД").catch(() => {});
        return;
      }
      
      console.log("✅ Event found:", event.event_name);
      
      if (event.is_closed === 1 && !["Not_go", "Sub", "Sub_all", "Sub_keeper"].includes(action)) {
        await ctx.answerCallbackQuery("Event is closed"); 
        return;
      }
      
      const current = await ctx.env.DB.prepare(
        "SELECT status, plus_count, keeper_plus_count FROM participants WHERE chat_id = ? AND message_id = ? AND user_id = ?"
      ).bind(chatId, msgId, userId).first() as any;

      let newStatus = current?.status || 'none';
      let newPlus = current?.plus_count || 0;
      let newKeeperPlus = current?.keeper_plus_count || 0;

      // Смена статуса НЕ трогает плюсы (как в оригинальном боте)
      if (action === "Go") { newStatus = "going"; }
      else if (action === "Go_keeper") { newStatus = "keeper"; }
      else if (action === "Not_go") { newStatus = "not_going"; }
      else if (action === "Not_sure") { newStatus = "not_sure"; }
      else if (action === "Add") { newPlus += 1; }
      else if (action === "Add_keeper") { newKeeperPlus += 1; }
      else if (action === "Sub") { if (newPlus > 0) newPlus -= 1; }
      else if (action === "Sub_keeper") { if (newKeeperPlus > 0) newKeeperPlus -= 1; }
      else if (action === "Sub_all") { newPlus = 0; } // вратарские плюсы не трогает

      console.log("💾 Updating DB: status=", newStatus, "plus=", newPlus, "keeperPlus=", newKeeperPlus);

      await ctx.env.DB.prepare(`
        INSERT INTO participants (chat_id, message_id, user_id, user_name, status, plus_count, keeper_plus_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, message_id, user_id) DO UPDATE SET
          status = excluded.status,
          plus_count = excluded.plus_count,
          keeper_plus_count = excluded.keeper_plus_count,
          user_name = excluded.user_name
      `).bind(chatId, msgId, userId, userLink, newStatus, newPlus, newKeeperPlus).run();

      console.log("🔨 Building new event text...");
      
      const newText = await buildEventText(
        ctx.env.DB, chatId, msgId, event.event_name,
        event.is_closed === 1, event.has_keepers === 1
      );
      
      console.log("📤 Editing message...");
      
      // grammY использует callbackQuery.message автоматически для editMessageText
      await ctx.editMessageText(newText, { 
        reply_markup: getKeyboard(event.is_closed === 1, event.has_keepers === 1), 
        parse_mode: "HTML" 
      });

      const answers: Record<string, string> = {
        Go: "✅ Going", Not_go: "❌ Not going", Not_sure: "💭 Not sure",
        Add: "➕ Add", Sub: "➖ Sub", Sub_all: "➖ Sub all",
        Go_keeper: "✅🥅 Going", Add_keeper: "➕🥅 Add", Sub_keeper: "➖🥅 Sub",
      };
      await ctx.answerCallbackQuery(answers[action] || "Updated");
      await logAction(ctx, action, `Message ID: ${msgId}`);
      
      console.log("✨ Callback processed successfully");
    } catch (err) {
      console.error("❌ Callback error:", err);
      await ctx.answerCallbackQuery("Error: " + (err as Error).message).catch(() => {});
    }
  });
}

// --- Экспорт Cloudflare Worker ---
export default {
  async fetch(request: Request, env: any, ctx: any): Promise<Response> {
    if (request.method === "GET") {
      return new Response("✅ Bot is running!", { status: 200 });
    }

    if (request.method === "POST") {
      try {
        const bot = new Bot<MyContext>(env.TELEGRAM_TOKEN);
        await bot.init(); 
        
        // 🔥 Передаем оригинальный env напрямую, не ломая прокси-объекты
        setupBot(bot, env);

        const update = await request.json() as any;
        await bot.handleUpdate(update);

        return new Response("OK", { status: 200 });
      } catch (err) {
        console.error("Worker exception:", err);
        return new Response("OK", { status: 200 }); 
      }
    }

    return new Response("Method not allowed", { status: 405 });
  },
};