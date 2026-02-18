"""
Телеграм-бот для диагностики API get_quotas.
Запускается по команде /start и показывает реальные данные из Google Script.
"""

import logging
import asyncio
import json
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ========== НАСТРОЙКИ ==========
TOKEN = "8598969347:AAEqsFqoW0sTO1yeKF49DHIB4-VlOsOESMQ"  # Вставьте токен тестового бота
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzK3aHBgGtbJPFIwT--6Z5mc-zlyFuOdZ0bp2GxdhZHCOIcMtOe1EGoQr0muNBAaDLs8w/exec"
# ===============================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

def test_get_quotas():
    """Прямой вызов API get_quotas и форматирование ответа"""
    payload = {"action": "get_quotas", "user_id": "1"}
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # Форматируем для красивого вывода
            if data.get("status") == "success":
                quotas = data.get("data", {}).get("quotas", {})
                msg = "✅ *Успешный ответ от Google Script*\n\n"
                msg += f"📊 Всего квот: {quotas.get('totalQuota')}\n"
                msg += f"✅ Использовано: {quotas.get('totalUsed')}\n"
                msg += f"⏳ Осталось: {quotas.get('remaining')}\n\n"
                msg += "*Детали по дням:*\n"
                for day, day_data in quotas.get("byDay", {}).items():
                    msg += f"📅 *{day}*: {day_data.get('used')}/{day_data.get('total')} (осталось {day_data.get('remaining')})\n"
                return msg, None
            else:
                return "❌ Ошибка в ответе Google Script", data.get("data")
        else:
            return f"❌ HTTP ошибка {response.status_code}", response.text[:200]
    except Exception as e:
        return "❌ Исключение", str(e)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer("🔍 *Тестирование API get_quotas*\nВыполняю запрос к Google Script...", parse_mode="Markdown")
    result, error = test_get_quotas()
    if error:
        await message.answer(f"{result}\n\n```\n{error}\n```", parse_mode="Markdown")
    else:
        await message.answer(result, parse_mode="Markdown")

async def main():
    print("Бот для диагностики запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
