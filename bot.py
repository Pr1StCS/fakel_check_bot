import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import csv
import datetime
import qrcode
from io import BytesIO

# Получение токена из переменных окружения (безопасно)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7045754365:AAEkE4KmwZqYZ199itjCdAYHl6MBRvmRdrg')

def generate_ticket_qr(order_data):
    """Генерирует QR-код для билета со ссылкой на бота"""
    # Создаем ссылку Telegram для быстрой проверки
    telegram_link = f"https://t.me/fakel_ticket_bot?start=check_{order_data['order_id']}"
    
    # Создаем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(telegram_link)
    qr.make(fit=True)
    
    # Создаем изображение
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Конвертируем в bytes для отправки в Telegram
    bio = BytesIO()
    bio.name = 'ticket.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)
    
    return bio

# Список ID администраторов
ADMIN_IDS = [5080055389, 847340378]  # Прист и Макс

# Состояния разговора
SELECTING_CATEGORY, SELECTING_QUANTITY, CONFIRMING = range(3)

# Категории билетов и цены
TICKETS = {
    "Стандарт": 1000,
    "VIP": 2500, 
    "Премиум": 5000
}

# Файл для хранения заказов
ORDERS_FILE = "orders.csv"

# Создаем файл заказов если его нет
def init_orders_file():
    if not os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(["Дата", "ID пользователя", "Имя пользователя", "Категория", "Количество", "Сумма", "ID заказа"])

# Команда /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем есть ли параметр в ссылке (deep link)
    if context.args and context.args[0].startswith('check_'):
        ticket_id = context.args[0].replace('check_', '')
        user_id = update.message.from_user.id
        
        # Если пользователь админ - проверяем билет
        if user_id in ADMIN_IDS:
            # Создаем фиктивный контекст для вызова check_ticket
            class FakeContext:
                args = [ticket_id]
            fake_context = FakeContext()
            await check_ticket(update, fake_context)
            return ConversationHandler.END
        else:
            # Для обычных пользователей показываем их билеты
            await my_tickets(update, context)
            return ConversationHandler.END
    
    print("=== НАЧАЛО РАЗГОВОРА ===")
    # Очищаем предыдущие данные
    context.user_data.clear()
    
    # Создаем клавиатуру с категориями
    keyboard = [list(TICKETS.keys())]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎫 Добро пожаловать в систему покупки билетов!\n"
        "Выберите категорию билета:",
        reply_markup=reply_markup
    )
    return SELECTING_CATEGORY

# Обработка выбора категории
async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text
    print(f"Выбрана категория: {category}")
    
    if category not in TICKETS:
        await update.message.reply_text("Пожалуйста, выберите категорию из предложенных:")
        return SELECTING_CATEGORY
    
    # Сохраняем выбранную категорию
    context.user_data['category'] = category
    context.user_data['price'] = TICKETS[category]
    
    await update.message.reply_text(
        f"🎟️ Вы выбрали: {category}\n"
        f"💵 Цена: {TICKETS[category]} руб.\n\n"
        "Введите количество билетов:"
    )
    return SELECTING_QUANTITY

# Обработка ввода количества
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text)
        print(f"Введено количество: {quantity}")
        
        if quantity <= 0:
            await update.message.reply_text("Введите число больше 0:")
            return SELECTING_QUANTITY
        
        # Сохраняем количество
        context.user_data['quantity'] = quantity
        total = context.user_data['price'] * quantity
        
        # Создаем клавиатуру для подтверждения
        keyboard = [["✅ Подтвердить", "❌ Отменить"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"📋 Ваш заказ:\n"
            f"🎟️ Категория: {context.user_data['category']}\n"
            f"🔢 Количество: {quantity}\n"
            f"💵 Сумма: {total} руб.\n\n"
            f"Подтверждаете заказ?",
            reply_markup=reply_markup
        )
        return CONFIRMING
        
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число:")
        return SELECTING_QUANTITY

# Обработка подтверждения заказа
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    print(f"Получен выбор: {choice}")
    
    if choice == "✅ Подтвердить":
        print("Начало сохранения заказа...")
        
        category = context.user_data['category']
        quantity = context.user_data['quantity']
        total = context.user_data['price'] * quantity
        
        # Сохраняем заказ в файл
        user = update.message.from_user
        order_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"{user.id}_{int(datetime.datetime.now().timestamp())}"

        print(f"Данные для сохранения: {category}, {quantity}, {total}")

        try:
            with open(ORDERS_FILE, 'a', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow([order_date, user.id, user.first_name, category, quantity, total, order_id])
            print("Заказ успешно сохранен в файл!")
            
            # Генерируем данные для QR-кода
            order_data = {
                'event': 'Концерт',
                'category': category,
                'quantity': quantity,
                'total': total,
                'order_id': order_id,
                'date': order_date
            }
            
            # Генерируем QR-код
            qr_image = generate_ticket_qr(order_data)
            
            # Отправляем QR-код
            await update.message.reply_photo(
                photo=qr_image,
                caption="🎫 Ваш электронный билет с QR-кодом\n\nСохраните его для входа на мероприятие!"
            )
            
        except Exception as e:
            print(f"Ошибка при сохранении: {e}")
        
        # Очищаем клавиатуру
        remove_keyboard = ReplyKeyboardRemove()
        
        await update.message.reply_text(
            f"🎉 Заказ подтвержден!\n\n"
            f"📋 Детали заказа:\n"
            f"🎟️ Категория: {category}\n"
            f"🔢 Количество: {quantity}\n"
            f"💵 Общая сумма: {total} руб.\n\n"
            f"Спасибо за покупку!",
            reply_markup=remove_keyboard
        )
        return ConversationHandler.END
        
    elif choice == "❌ Отменить":
        # Очищаем клавиатуру
        remove_keyboard = ReplyKeyboardRemove()
        
        await update.message.reply_text(
            "Заказ отменен. Используйте /start для нового заказа.",
            reply_markup=remove_keyboard
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, выберите вариант из кнопок:")
        return CONFIRMING

# Обработка отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Покупка отменена",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📋 *Доступные команды:*

Для всех:
/start - Купить билеты
/my_tickets - Мои билеты
/help - Помощь

Для администраторов:
/admin - Просмотр заказов  
/stats - Статистика
/check_ticket <ID> - Проверить билет
/use_ticket <ID> - Использовать билет
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Тестовая команда
async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("=== ТЕСТОВАЯ КОМАНДА ВЫЗВАНА ===")
    await update.message.reply_text("Тест: бот работает!")

# Команда для получения ID
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    response = (
        f"🔍 Ваши данные:\n"
        f"ID: {user.id}\n"
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username}"
    )
    print(f"ID пользователя: {user.id}")
    await update.message.reply_text(response)

# Просмотр всех заказов
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            orders = list(reader)
            
        if len(orders) <= 1:
            await update.message.reply_text("📊 Заказов пока нет")
            return
            
        total_orders = len(orders) - 1
        total_revenue = sum(int(order[5]) for order in orders[1:])
        
        response = f"📊 Статистика заказов:\n\n"
        response += f"📈 Всего заказов: {total_orders}\n"
        response += f"💰 Общая выручка: {total_revenue} руб.\n\n"
        response += "📋 Последние заказы:\n"
        
        # Показываем последние 5 заказов
        for order in orders[-5:]:
            response += f"┌ {order[0]}\n"
            response += f"├ 👤 {order[2]} (ID: {order[1]})\n"
            response += f"├ 🎟️ {order[3]} x {order[4]}\n"
            response += f"└ 💵 {order[5]} руб.\n\n"
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# Просмотр полной статистики
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            orders = list(reader)
            
        if len(orders) <= 1:
            await update.message.reply_text("📊 Заказов пока нет")
            return
        
        # Статистика по категориям
        categories = {}
        for order in orders[1:]:
            category = order[3]
            quantity = int(order[4])
            revenue = int(order[5])
            
            if category not in categories:
                categories[category] = {'quantity': 0, 'revenue': 0}
            
            categories[category]['quantity'] += quantity
            categories[category]['revenue'] += revenue
        
        total_orders = len(orders) - 1
        total_revenue = sum(int(order[5]) for order in orders[1:])
        
        response = f"📊 Детальная статистика:\n\n"
        response += f"📈 Всего заказов: {total_orders}\n"
        response += f"💰 Общая выручка: {total_revenue} руб.\n\n"
        
        response += "📊 По категориям:\n"
        for category, stats in categories.items():
            response += f"🎟️ {category}:\n"
            response += f"   ├ Продано: {stats['quantity']} шт.\n"
            response += f"   └ Выручка: {stats['revenue']} руб.\n\n"
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# Проверка билета по ID
async def check_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /check_ticket <ID_билета>")
        return
    
    ticket_id = context.args[0]
    print(f"=== ПРОВЕРКА БИЛЕТА ===")
    print(f"Ищем билет с ID: {ticket_id}")
    
    try:
        # Ищем билет в заказах
        with open(ORDERS_FILE, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            orders = list(reader)
        
        print(f"Всего заказов в файле: {len(orders)}")
        
        ticket_info = None
        for order in orders[1:]:  # Пропускаем заголовок
            # Для новых заказов (8 колонок)
            if len(order) >= 8 and order[7] == ticket_id:
                ticket_info = {
                    'date': order[0],
                    'user_name': order[2],
                    'category': order[3],
                    'quantity': order[4],
                    'total': order[5],
                    'order_id': order[7]
                }
                break
            # Для старых заказов (7 колонок)  
            elif len(order) >= 7 and order[6] == ticket_id:
                ticket_info = {
                    'date': order[0],
                    'user_name': order[2],
                    'category': order[3],
                    'quantity': order[4],
                    'total': order[5],
                    'order_id': order[6]
                }
                break
        
        if not ticket_info:
            print("Билет не найден в файле!")
            await update.message.reply_text(
                f"❌ Билет с ID `{ticket_id}` не найден",
                parse_mode='Markdown'
            )
            return
        
        # Проверяем использован ли билет
        used_tickets_file = "used_tickets.csv"
        is_used = False
        
        if os.path.exists(used_tickets_file):
            with open(used_tickets_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0] == ticket_id:
                        is_used = True
                        break
        
        response = f"🎫 *Проверка билета*\n\n"
        response += f"🔍 *ID билета:* `{ticket_id}`\n"
        response += f"👤 *Владелец:* {ticket_info['user_name']}\n"
        response += f"🎟️ *Категория:* {ticket_info['category']}\n"
        response += f"🔢 *Количество:* {ticket_info['quantity']} шт.\n"
        response += f"💰 *Сумма:* {ticket_info['total']} руб.\n"
        response += f"📅 *Дата покупки:* {ticket_info['date']}\n\n"
        
        if is_used:
            response += "❌ *Статус:* БИЛЕТ УЖЕ ИСПОЛЬЗОВАН"
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            response += "✅ *Статус:* БИЛЕТ ДЕЙСТВИТЕЛЕН"
            
            # Создаем клавиатуру с кнопкой "Использовать билет"
            keyboard = [[f"✅ Использовать билет {ticket_id}"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при проверке: {e}")

# Отметка билета как использованного
async def use_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /use_ticket <ID_билета>")
        return
    
    ticket_id = context.args[0]
    
    try:
        # Создаем файл использованных билетов если его нет
        used_tickets_file = "used_tickets.csv"
        if not os.path.exists(used_tickets_file):
            with open(used_tickets_file, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["order_id", "used_date", "verified_by"])
        
        # Проверяем существует ли билет
        with open(ORDERS_FILE, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            orders = list(reader)

        ticket_exists = False
        for order in orders[1:]:
            # Для новых заказов (8 колонок)
            if len(order) >= 8 and order[7] == ticket_id:
                ticket_exists = True
                break
            # Для старых заказов (7 колонок)  
            elif len(order) >= 7 and order[6] == ticket_id:
                ticket_exists = True
                break
        
        if not ticket_exists:
            await update.message.reply_text(f"❌ Билет с ID `{ticket_id}` не найден")
            return
        
        # Проверяем не использован ли уже билет
        already_used = False
        with open(used_tickets_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0] == ticket_id:
                    already_used = True
                    break
        
        if already_used:
            await update.message.reply_text(f"❌ Билет `{ticket_id}` уже использован")
            return
        
        # Отмечаем билет как использованный
        used_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(used_tickets_file, 'a', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([ticket_id, used_date, user_id])
        
        await update.message.reply_text(
            f"✅ Билет `{ticket_id}` отмечен как использованный\n"
            f"📅 Время: {used_date}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# Обработка нажатия кнопки "Использовать билет"
async def use_ticket_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print(f"=== ОБРАБОТКА КНОПКИ ===")
    print(f"Текст кнопки: {text}")
    
    if text.startswith("✅ Использовать билет "):
        ticket_id = text.replace("✅ Использовать билет ", "").strip()
        print(f"Извлеченный ID билета: {ticket_id}")
        
        # Создаем фиктивный контекст для вызова use_ticket
        class FakeContext:
            args = [ticket_id]
        fake_context = FakeContext()
        
        await use_ticket(update, fake_context)
        
        # Убираем клавиатуру без сообщения
        await update.message.edit_reply_markup(reply_markup=None)

# Просмотр своих билетов
async def my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    try:
        with open(ORDERS_FILE, 'r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            orders = list(reader)
        
        user_tickets = []
        for order in orders[1:]:  # Пропускаем заголовок
            if len(order) > 2 and int(order[1]) == user_id:
                user_tickets.append({
                    'date': order[0],
                    'category': order[3],
                    'quantity': order[4],
                    'total': order[5],
                    'order_id': order[7] if len(order) >= 8 else order[6]
                })
        
        if not user_tickets:
            await update.message.reply_text("🎫 У вас пока нет купленных билетов")
            return
        
        response = "🎫 *Ваши билеты*\n\n"
        
        for i, ticket in enumerate(user_tickets, 1):
            response += f"*Билет #{i}*\n"
            response += f"🎟️ Категория: {ticket['category']}\n"
            response += f"🔢 Количество: {ticket['quantity']} шт.\n"
            response += f"💰 Сумма: {ticket['total']} руб.\n"
            response += f"📅 Дата покупки: {ticket['date']}\n"
            response += f"🔍 ID билета: `{ticket['order_id']}`\n\n"
        
        response += "ℹ️ Для проверки билета покажите QR-код администратору"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Ошибка: {context.error}")

def main():
    # Инициализируем файл заказов
    init_orders_file()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ПОТОМ добавляем ConversationHandler (СНАЧАЛА!)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            SELECTING_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_category)
            ],
            SELECTING_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_quantity)
            ],
            CONFIRMING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv_handler)
    
    # Сначала добавляем обычные команды (ПОСЛЕ ConversationHandler!)
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("admin", admin_orders))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(CommandHandler("check_ticket", check_ticket))
    app.add_handler(CommandHandler("use_ticket", use_ticket))
    app.add_handler(CommandHandler("my_tickets", my_tickets))
    
    # Добавляем обработчик кнопок (ПОСЛЕ всех CommandHandler!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, use_ticket_button))
    
    app.add_error_handler(error_handler)
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()