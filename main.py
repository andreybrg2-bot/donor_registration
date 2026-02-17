"""
🎯 БОТ ДЛЯ ЗАПИСИ НА ДОНОРСТВО КРОВИ
Версия: 3.5 (ИСПРАВЛЕНА ОШИБКА С F-СТРОКАМИ)
Автор: AI Assistant
Дата: 2024

ОСНОВНЫЕ ИСПРАВЛЕНИЯ:
✅ Исправлены f-строки с обратными слешами
✅ get_stats - исправлена обработка ответа от Google Script
✅ get_quotas - добавлена поддержка API квот
✅ get_free_times - исправлена структура запроса
✅ check_existing - исправлена обработка ответа
✅ register - исправлена структура запроса
✅ cancel_booking - исправлена структура запроса
✅ get_user_bookings - исправлена обработка ответа
✅ get_available_dates - исправлена структура ответа
"""

import logging
import asyncio
import json
import time
import random
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, CallbackQuery
)
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== НАСТРОЙКИ ==========
TOKEN = "8598969347:AAEqsFqoW0sTO1yeKF49DHIB4-VlOsOESMQ"

# Режим работы (LOCAL, GOOGLE, HYBRID)
MODE = "GOOGLE"

# URL вашего Google Apps Script
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbz5P0rWI_wq_kJyWTnPD0V-OwDk61j2EcSJ40OZ2ZxqUKckATNNUad7-INAwAgKOd9REg/exec"

# ID администраторов
ADMIN_IDS = [5097581039]

# Таймаут сессии в секундах (10 минут)
SESSION_TIMEOUT = 600

# ========== КЛИЕНТ GOOGLE SCRIPT ==========
class GoogleScriptClient:
    """Клиент для работы с Google Apps Script"""
    
    def __init__(self, script_url: str):
        self.script_url = script_url
        self.session = requests.Session()
        self.session.verify = False
        self.timeout = 15
        self.cache = {}
        self.cache_time = {}
    
    def test_connection(self) -> dict:
        """Проверить соединение с Google Script"""
        try:
            print(f"[GOOGLE] 🔗 Тестирование соединения...")
            response = self.session.post(
                self.script_url,
                json={"action": "test"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"[GOOGLE] ✅ Соединение успешно: {data.get('status')}")
                    return data
                except json.JSONDecodeError:
                    print(f"[GOOGLE] ❌ Неверный JSON ответ")
                    return {"status": "error", "data": "Неверный формат ответа"}
            else:
                print(f"[GOOGLE] ❌ HTTP ошибка: {response.status_code}")
                return {"status": "error", "data": f"HTTP ошибка: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            print("[GOOGLE] ⏱️ Таймаут подключения")
            return {"status": "error", "data": "Таймаут подключения к Google Script"}
        except requests.exceptions.ConnectionError:
            print("[GOOGLE] 🔌 Ошибка соединения")
            return {"status": "error", "data": "Ошибка соединения с Google Script"}
        except Exception as e:
            print(f"[GOOGLE] ❌ Неизвестная ошибка: {str(e)}")
            return {"status": "error", "data": f"Неизвестная ошибка: {str(e)}"}
    
    def call_api(self, action: str, data: dict = None, user_id: int = None, force_refresh: bool = False) -> dict:
        """Вызвать API Google Script с кэшированием"""
        if data is None:
            data = {}
        
        if force_refresh:
            print(f"[GOOGLE] 🔄 Принудительное обновление кэша для {action}")
            cache_keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{action}_")]
            for key in cache_keys_to_delete:
                self.cache.pop(key, None)
                self.cache_time.pop(key, None)
        else:
            cache_key = f"{action}_{user_id}_{json.dumps(data, sort_keys=True)}"
            
            if action in ["get_available_dates", "get_stats", "get_quotas"]:
                if cache_key in self.cache:
                    cache_age = time.time() - self.cache_time.get(cache_key, 0)
                    if cache_age < 300:
                        print(f"[GOOGLE] 💾 Используем кэшированные данные для {action}")
                        return self.cache[cache_key]
        
        try:
            payload = {"action": action, **data}
            if user_id:
                payload["user_id"] = str(user_id)
            
            print(f"[GOOGLE] 📤 {action}: {data}")
            response = self.session.post(
                self.script_url,
                json=payload,
                timeout=self.timeout
            )
            
            print(f"[GOOGLE] 📥 Ответ: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"[GOOGLE] ✅ Успешно: {result.get('status')}")
                    
                    if action in ["get_available_dates", "get_stats", "get_quotas"] and not force_refresh:
                        cache_key = f"{action}_{user_id}_{json.dumps(data, sort_keys=True)}"
                        self.cache[cache_key] = result
                        self.cache_time[cache_key] = time.time()
                    
                    return result
                except json.JSONDecodeError as e:
                    print(f"[GOOGLE] ❌ JSON ошибка: {str(e)}")
                    return {"status": "error", "data": "Неверный формат ответа от Google Script"}
            else:
                print(f"[GOOGLE] ❌ HTTP ошибка: {response.status_code}")
                return {"status": "error", "data": f"HTTP ошибка: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            print("[GOOGLE] ⏱️ Таймаут запроса")
            return {"status": "error", "data": "Таймаут подключения к Google Script"}
        except requests.exceptions.ConnectionError:
            print("[GOOGLE] 🔌 Ошибка соединения")
            return {"status": "error", "data": "Ошибка соединения с Google Script"}
        except Exception as e:
            print(f"[GOOGLE] ❌ Неизвестная ошибка: {str(e)}")
            return {"status": "error", "data": f"Неизвестная ошибка: {str(e)}"}

# Инициализируем клиент Google Script
google_client = GoogleScriptClient(GOOGLE_SCRIPT_URL)

# ========== ЛОКАЛЬНОЕ ХРАНИЛИЩЕ ==========
class LocalStorage:
    """Локальное хранилище данных для автономного режима"""
    
    def __init__(self):
        self.reset_data()
        print("[LOCAL] 💾 Локальное хранилище инициализировано (v3.5)")
        
    def reset_data(self):
        """Сбросить все данные"""
        self.bookings = {}
        self.quotas = {
            "понедельник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "вторник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "среда": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "четверг": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "пятница": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "суббота": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4},
            "воскресенье": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4}
        }
        self.working_hours = [
            "07:30", "08:00", "08:30", "09:00", "09:30", "10:00",
            "10:30", "11:00", "11:30", "12:00", "12:30", "13:00",
            "13:30", "14:00"
        ]
        
        self._add_test_data()
    
    def _add_test_data(self):
        """Добавить тестовые данные"""
        today = datetime.now()
        test_dates = []
        for i in range(1, 8):
            test_date = today + timedelta(days=i)
            test_dates.append(test_date.strftime("%Y-%m-%d"))
        
        test_data = [
            (111111, test_dates[0], "09:00", "A+", "понедельник"),
            (222222, test_dates[1], "10:30", "B-", "вторник"),
            (333333, test_dates[4], "11:00", "O+", "пятница"),
        ]
        
        for user_id, date, time_slot, blood_group, day in test_data:
            self._add_booking(user_id, date, time_slot, blood_group, day)
        
        print(f"[LOCAL] 📊 Добавлено {len(test_data)} тестовых записей")
    
    def _add_booking(self, user_id: int, date: str, time_slot: str, blood_group: str, day: str):
        """Внутренняя функция добавления записи"""
        if user_id not in self.bookings:
            self.bookings[user_id] = {}
        
        ticket = f"Т-{day[:3]}-{blood_group}-{random.randint(1000, 9999)}"
        self.bookings[user_id][date] = {
            "ticket": ticket,
            "time": time_slot,
            "blood_group": blood_group,
            "day": day,
            "created_at": datetime.now().isoformat()
        }
    
    def get_available_dates(self, user_id: int) -> dict:
        """Получить доступные даты"""
        today = datetime.now()
        available_dates = []
        
        for i in range(1, 31):
            if len(available_dates) >= 6:
                break
                
            check_date = today + timedelta(days=i)
            day_of_week = self._get_day_of_week_ru(check_date)
            
            if day_of_week in self.quotas:
                day_quotas = self.quotas[day_of_week]
                has_quota = any(quota > 0 for quota in day_quotas.values())
                
                if has_quota:
                    date_info = {
                        "date": check_date.strftime("%Y-%m-%d"),
                        "day_of_week": day_of_week,
                        "display_date": check_date.strftime("%d.%m.%Y"),
                        "day_of_week_short": day_of_week[:3],
                        "timestamp": int(check_date.timestamp())
                    }
                    available_dates.append(date_info)
        
        return {
            "status": "success",
            "data": {
                "available_dates": available_dates,
                "message": f"Найдено {len(available_dates)} доступных дат",
                "count": len(available_dates)
            }
        }
    
    def _get_day_of_week_ru(self, date_obj: datetime) -> str:
        """Получить день недели на русском"""
        days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        return days[date_obj.weekday()]
    
def get_free_times(date: str, blood_group: str) -> dict:
    """Универсальная функция получения свободного времени"""
    if MODE == "LOCAL":
        return local_storage.get_free_times(date, blood_group)
    elif MODE == "GOOGLE":
        result = google_client.call_api("get_free_times", {"date": date, "blood_group": blood_group}, force_refresh=True)
        # Нормализуем ответ
        if result["status"] == "success":
            if "data" in result:
                data = result["data"]
                # Проверяем, что quota - это число
                if "quota" not in data or not isinstance(data["quota"], (int, float)):
                    # Если квота не пришла, вычисляем из quota_total и quota_used
                    quota_total = data.get("quota_total", 0)
                    quota_used = data.get("quota_used", 0)
                    data["quota"] = max(0, quota_total - quota_used)
        return result
    elif MODE == "HYBRID":
        result = google_client.call_api("get_free_times", {"date": date, "blood_group": blood_group}, force_refresh=True)
        
        if result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, переключаемся на локальное хранилище")
            return local_storage.get_free_times(date, blood_group)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}
    
    def check_existing(self, date: str, user_id: int) -> dict:
        """Проверить существующую запись на конкретную дату"""
        if user_id in self.bookings and date in self.bookings[user_id]:
            booking = self.bookings[user_id][date]
            return {
                "status": "success",
                "data": {
                    "exists": True,
                    "ticket": booking["ticket"],
                    "time": booking["time"],
                    "blood_group": booking["blood_group"],
                    "day": booking["day"],
                    "date": date
                }
            }
        else:
            return {
                "status": "success",
                "data": {
                    "exists": False,
                    "ticket": None,
                    "time": None,
                    "blood_group": None
                }
            }
    
    def register(self, date: str, blood_group: str, time_slot: str, user_id: int) -> dict:
        """Зарегистрировать новую запись"""
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_of_week = self._get_day_of_week_ru(date_obj)
        except ValueError:
            return {"status": "error", "data": f"Неверный формат даты: {date}"}
        
        existing = self.check_existing(date, user_id)
        if existing["data"]["exists"]:
            return {
                "status": "error",
                "data": f"У вас уже есть запись на {date}. Талон: {existing['data']['ticket']}"
            }
        
        for user_data in self.bookings.values():
            if date in user_data and user_data[date]["time"] == time_slot and user_data[date]["blood_group"] == blood_group:
                return {
                    "status": "error",
                    "data": f"Время {time_slot} на {date} для группы крови {blood_group} уже занято."
                }
        
        if day_of_week not in self.quotas or blood_group not in self.quotas[day_of_week]:
            return {"status": "error", "data": f"Нет квот для {day_of_week}, группа {blood_group}"}
        
        busy_count = 0
        for user_data in self.bookings.values():
            if date in user_data and user_data[date]["blood_group"] == blood_group:
                busy_count += 1
        
        if busy_count >= self.quotas[day_of_week][blood_group]:
            return {
                "status": "error",
                "data": f"На {date} для группы крови {blood_group} все квоты заняты."
            }
        
        ticket = f"Т-{day_of_week[:3]}-{blood_group}-{random.randint(1000, 9999)}"
        
        if user_id not in self.bookings:
            self.bookings[user_id] = {}
        
        self.bookings[user_id][date] = {
            "ticket": ticket,
            "time": time_slot,
            "blood_group": blood_group,
            "day": day_of_week,
            "created_at": datetime.now().isoformat()
        }
        
        quota_remaining = self.quotas[day_of_week][blood_group] - (busy_count + 1)
        quota_total = self.quotas[day_of_week][blood_group]
        quota_used = busy_count + 1
        
        return {
            "status": "success",
            "data": {
                "ticket": ticket,
                "day": day_of_week,
                "date": date,
                "time": time_slot,
                "blood_group": blood_group,
                "quota_remaining": quota_remaining,
                "quota_total": quota_total,
                "quota_used": quota_used,
                "registration_date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            }
        }
    
    def cancel_booking(self, date: str, ticket: str, user_id: int) -> dict:
        """Отменить запись"""
        if user_id in self.bookings and date in self.bookings[user_id]:
            booking = self.bookings[user_id][date]
            
            if booking["ticket"] == ticket:
                del self.bookings[user_id][date]
                
                if not self.bookings[user_id]:
                    del self.bookings[user_id]
                
                return {
                    "status": "success",
                    "data": {
                        "message": "Запись успешно отменена",
                        "ticket": ticket,
                        "day": booking["day"],
                        "date": date,
                        "time": booking["time"],
                        "blood_group": booking["blood_group"]
                    }
                }
        
        return {
            "status": "error",
            "data": "Запись не найдена. Проверьте дату и номер талона."
        }
    
    def get_user_bookings(self, user_id: int) -> dict:
        """Получить все записи пользователя"""
        if user_id in self.bookings:
            bookings_list = []
            for date, booking in self.bookings[user_id].items():
                bookings_list.append({
                    "date": date,
                    "day": booking["day"],
                    "ticket": booking["ticket"],
                    "time": booking["time"],
                    "blood_group": booking["blood_group"]
                })
            
            return {
                "status": "success",
                "data": {
                    "bookings": bookings_list,
                    "count": len(bookings_list)
                }
            }
        else:
            return {
                "status": "success",
                "data": {
                    "bookings": [],
                    "count": 0
                }
            }
    
    def get_quotas(self) -> dict:
        """Получить информацию о квотах"""
        total_quota = 0
        total_used = 0
        by_day = {}
        
        for day, quotas in self.quotas.items():
            day_total = sum(quotas.values())
            day_used = 0
            
            for user_data in self.bookings.values():
                for date, booking in user_data.items():
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    booking_day = self._get_day_of_week_ru(date_obj)
                    if booking_day == day:
                        day_used += 1
            
            total_quota += day_total
            total_used += day_used
            
            by_day[day] = {
                "total": day_total,
                "used": day_used,
                "remaining": day_total - day_used,
                "quotas": quotas
            }
        
        return {
            "status": "success",
            "data": {
                "quotas": {
                    "totalQuota": total_quota,
                    "totalUsed": total_used,
                    "remaining": total_quota - total_used,
                    "byDay": by_day
                },
                "message": f"Всего квот: {total_quota}, использовано: {total_used}, осталось: {total_quota - total_used}"
            }
        }
    
    def get_stats(self) -> dict:
        """Получить статистику"""
        total_bookings = sum(len(user_bookings) for user_bookings in self.bookings.values())
        total_users = len(self.bookings)
        
        day_stats = {}
        blood_group_stats = {}
        
        for user_data in self.bookings.values():
            for date, booking in user_data.items():
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                day = self._get_day_of_week_ru(date_obj)
                day_stats[day] = day_stats.get(day, 0) + 1
                
                blood_group = booking["blood_group"]
                blood_group_stats[blood_group] = blood_group_stats.get(blood_group, 0) + 1
        
        most_popular_day = max(day_stats.items(), key=lambda x: x[1])[0] if day_stats else "нет данных"
        most_popular_blood = max(blood_group_stats.items(), key=lambda x: x[1])[0] if blood_group_stats else "нет данных"
        
        quota_stats = self.get_quotas()["data"]["quotas"]
        
        return {
            "status": "success",
            "data": {
                "total_bookings": total_bookings,
                "total_users": total_users,
                "day_stats": day_stats,
                "blood_group_stats": blood_group_stats,
                "most_popular_day": most_popular_day,
                "most_popular_blood_group": most_popular_blood,
                "quota_stats": quota_stats
            }
        }

# Инициализируем локальное хранилище
local_storage = LocalStorage()

# ========== СЕРВИС ДЛЯ ТАЙМАУТА СЕССИЙ ==========
class SessionTimeout:
    """Управление таймаутом сессий"""
    
    def __init__(self, timeout_seconds: int = SESSION_TIMEOUT):
        self.timeout_seconds = timeout_seconds
        self.user_last_activity: Dict[int, float] = {}
    
    def update_activity(self, user_id: int):
        """Обновить время последней активности пользователя"""
        self.user_last_activity[user_id] = time.time()
    
    def is_session_expired(self, user_id: int) -> bool:
        """Проверить, истекла ли сессия пользователя"""
        if user_id not in self.user_last_activity:
            return False
        
        last_activity = self.user_last_activity[user_id]
        time_since_last_activity = time.time() - last_activity
        
        return time_since_last_activity > self.timeout_seconds
    
    def clear_session(self, user_id: int):
        """Очистить данные сессии пользователя"""
        if user_id in self.user_last_activity:
            del self.user_last_activity[user_id]

# Инициализируем сервис таймаута
session_timeout = SessionTimeout()

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ТАЙМАУТА ==========
async def timeout_middleware(handler, event, data):
    """Middleware для проверки таймаута сессии"""
    try:
        user_id = None
        chat_id = None
        
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
            chat_id = event.chat.id if hasattr(event, 'chat') and event.chat else None
        elif hasattr(event, 'message') and event.message and event.message.from_user:
            user_id = event.message.from_user.id
            chat_id = event.message.chat.id
        elif hasattr(event, 'callback_query') and event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
            if hasattr(event.callback_query, 'message') and event.callback_query.message:
                chat_id = event.callback_query.message.chat.id
        
        if user_id:
            if session_timeout.is_session_expired(user_id):
                print(f"[TIMEOUT] ⏰ Сессия пользователя {user_id} истекла")
                
                state = data.get('state')
                if state:
                    await state.clear()
                
                session_timeout.clear_session(user_id)
                
                bot = data.get('bot')
                
                is_main_menu_callback = (
                    hasattr(event, 'callback_query') and 
                    event.callback_query and 
                    hasattr(event.callback_query, 'data') and
                    event.callback_query.data == "main_menu"
                )
                
                if is_main_menu_callback:
                    print(f"[TIMEOUT] 🔄 Игнорируем таймаут для кнопки главного меню")
                    session_timeout.update_activity(user_id)
                    return await handler(event, data)
                
                if bot and chat_id:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="⏳ Ваша сессия истекла из-за неактивности.\n\n"
                                 "Для продолжения работы используйте команду /start",
                            reply_markup=get_main_menu_keyboard()
                        )
                    except Exception as e:
                        print(f"[TIMEOUT] ❌ Ошибка отправки сообщения: {e}")
                
                if hasattr(event, 'callback_query'):
                    try:
                        await event.callback_query.answer(
                            "Сессия истекла. Используйте /start",
                            show_alert=True
                        )
                    except Exception as e:
                        print(f"[TIMEOUT] ❌ Ошибка ответа на callback: {e}")
                
                return False
            
            session_timeout.update_activity(user_id)
    
    except Exception as e:
        print(f"[TIMEOUT] ❌ Ошибка в middleware: {e}")
    
    return await handler(event, data)

# ========== УНИВЕРСАЛЬНЫЙ API (ИСПРАВЛЕНО ДЛЯ GOOGLE ТАБЛИЦ) ==========
def get_available_dates(user_id: int, force_refresh: bool = False) -> dict:
    """Универсальная функция получения доступных дат"""
    if MODE == "LOCAL":
        return local_storage.get_available_dates(user_id)
    elif MODE == "GOOGLE":
        return google_client.call_api("get_available_dates", {}, user_id, force_refresh)
    elif MODE == "HYBRID":
        result = google_client.call_api("get_available_dates", {}, user_id, force_refresh)
        
        if result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, переключаемся на локальное хранилище")
            return local_storage.get_available_dates(user_id)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def get_free_times(date: str, blood_group: str) -> dict:
    """Универсальная функция получения свободного времени"""
    if MODE == "LOCAL":
        return local_storage.get_free_times(date, blood_group)
    elif MODE == "GOOGLE":
        return google_client.call_api("get_free_times", {"date": date, "blood_group": blood_group})
    elif MODE == "HYBRID":
        result = google_client.call_api("get_free_times", {"date": date, "blood_group": blood_group})
        
        if result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, переключаемся на локальное хранилище")
            return local_storage.get_free_times(date, blood_group)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def check_existing(date: str, user_id: int) -> dict:
    """Универсальная функция проверки записи"""
    if MODE == "LOCAL":
        return local_storage.check_existing(date, user_id)
    elif MODE == "GOOGLE":
        result = google_client.call_api("check_existing", {"date": date}, user_id)
        # Нормализуем ответ от Google Script
        if result["status"] == "success":
            if "data" in result and isinstance(result["data"], dict):
                if "exists" not in result["data"]:
                    # Преобразуем ответ в ожидаемый формат
                    booking = result["data"]
                    result["data"] = {
                        "exists": True,
                        "ticket": booking.get("ticket"),
                        "time": booking.get("time"),
                        "blood_group": booking.get("blood_group"),
                        "day": booking.get("day"),
                        "date": date
                    }
        return result
    elif MODE == "HYBRID":
        result = google_client.call_api("check_existing", {"date": date}, user_id)
        
        if result["status"] == "error":
            return local_storage.check_existing(date, user_id)
        
        # Нормализуем ответ
        if result["status"] == "success":
            if "data" in result and isinstance(result["data"], dict):
                if "exists" not in result["data"]:
                    booking = result["data"]
                    result["data"] = {
                        "exists": True,
                        "ticket": booking.get("ticket"),
                        "time": booking.get("time"),
                        "blood_group": booking.get("blood_group"),
                        "day": booking.get("day"),
                        "date": date
                    }
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def register(date: str, blood_group: str, time_slot: str, user_id: int) -> dict:
    """Универсальная функция регистрации"""
    if MODE == "LOCAL":
        return local_storage.register(date, blood_group, time_slot, user_id)
    elif MODE == "GOOGLE":
        return google_client.call_api("register", {
            "date": date,
            "blood_group": blood_group,
            "time": time_slot
        }, user_id)
    elif MODE == "HYBRID":
        result = google_client.call_api("register", {
            "date": date,
            "blood_group": blood_group,
            "time": time_slot
        }, user_id)
        
        if result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, сохраняем локально")
            return local_storage.register(date, blood_group, time_slot, user_id)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def cancel_booking(date: str, ticket: str, user_id: int) -> dict:
    """Универсальная функция отмены записи"""
    if MODE == "LOCAL":
        return local_storage.cancel_booking(date, ticket, user_id)
    elif MODE == "GOOGLE":
        return google_client.call_api("cancel_booking", {
            "date": date,
            "ticket": ticket
        }, user_id)
    elif MODE == "HYBRID":
        result = google_client.call_api("cancel_booking", {
            "date": date,
            "ticket": ticket
        }, user_id)
        
        if result["status"] == "error":
            return local_storage.cancel_booking(date, ticket, user_id)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def get_user_bookings(user_id: int) -> dict:
    """Универсальная функция получения записей пользователя"""
    if MODE == "LOCAL":
        return local_storage.get_user_bookings(user_id)
    elif MODE in ["GOOGLE", "HYBRID"]:
        # Принудительно запрашиваем свежие данные, игнорируя кэш
        result = google_client.call_api("get_user_bookings", {}, user_id, force_refresh=True)
        
        # Нормализуем ответ от Google Script
        if result["status"] == "success":
            if "data" in result:
                if isinstance(result["data"], list):
                    # Преобразуем список записей в ожидаемый формат
                    bookings_list = []
                    for booking in result["data"]:
                        if isinstance(booking, dict):
                            bookings_list.append({
                                "date": booking.get("date", ""),
                                "day": booking.get("day", ""),
                                "ticket": booking.get("ticket", ""),
                                "time": booking.get("time", ""),
                                "blood_group": booking.get("blood_group", "")
                            })
                    result["data"] = {
                        "bookings": bookings_list,
                        "count": len(bookings_list)
                    }
                elif isinstance(result["data"], dict) and "bookings" not in result["data"]:
                    # Если пришел объект с записями, но не в нужном формате
                    bookings_list = []
                    for date, booking in result["data"].items():
                        if isinstance(booking, dict):
                            bookings_list.append({
                                "date": date,
                                "day": booking.get("day", ""),
                                "ticket": booking.get("ticket", ""),
                                "time": booking.get("time", ""),
                                "blood_group": booking.get("blood_group", "")
                            })
                    result["data"] = {
                        "bookings": bookings_list,
                        "count": len(bookings_list)
                    }
        
        if MODE == "HYBRID" and (result["status"] == "error" or 
                                 (result["status"] == "success" and 
                                  isinstance(result.get("data"), dict) and 
                                  result["data"].get("count", 0) == 0 and
                                  user_id in local_storage.bookings)):
            # Если в Google нет записей, но есть локально - используем локальные
            return local_storage.get_user_bookings(user_id)
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def get_quotas() -> dict:
    """Универсальная функция получения квот (ИСПРАВЛЕНО)"""
    if MODE == "LOCAL":
        return local_storage.get_quotas()
    elif MODE in ["GOOGLE", "HYBRID"]:
        # Принудительно запрашиваем свежие данные, игнорируя кэш
        result = google_client.call_api("get_quotas", {}, force_refresh=True)
        
        if MODE == "HYBRID" and result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, используем локальные квоты")
            return local_storage.get_quotas()
        
        # Если Google Script вернул ошибку или пустые данные
        if result["status"] == "error" or not result.get("data"):
            print(f"[GOOGLE] ⚠️ Получены некорректные данные квот, используем локальные квоты")
            return local_storage.get_quotas()
        
        # Нормализуем ответ от Google Script
        if result["status"] == "success" and "data" in result:
            data = result["data"]
            if isinstance(data, dict) and "quotas" in data:
                # Убеждаемся, что структура правильная
                quotas_data = data["quotas"]
                if isinstance(quotas_data, dict):
                    if "totalQuota" not in quotas_data:
                        quotas_data["totalQuota"] = 0
                    if "totalUsed" not in quotas_data:
                        quotas_data["totalUsed"] = 0
                    if "remaining" not in quotas_data:
                        quotas_data["remaining"] = quotas_data.get("totalQuota", 0) - quotas_data.get("totalUsed", 0)
                    if "byDay" not in quotas_data:
                        quotas_data["byDay"] = {}
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def get_stats() -> dict:
    """Универсальная функция получения статистики"""
    if MODE == "LOCAL":
        return local_storage.get_stats()
    elif MODE in ["GOOGLE", "HYBRID"]:
        # Принудительно запрашиваем свежие данные, игнорируя кэш
        result = google_client.call_api("get_stats", {}, force_refresh=True)
        
        # 🔍 ОТЛАДКА: выводим реальную структуру данных
        print(f"[DEBUG] get_stats - статус: {result.get('status')}")
        print(f"[DEBUG] get_stats - полный ответ: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
        
        if MODE == "HYBRID" and result["status"] == "error":
            print(f"[HYBRID] 🔄 Google Script недоступен, используем локальную статистику")
            return local_storage.get_stats()
        
        # Если Google Script вернул ошибку или пустые данные
        if result["status"] == "error" or not result.get("data"):
            print(f"[GOOGLE] ⚠️ Получены некорректные данные, используем локальную статистику")
            return local_storage.get_stats()
        
        # Нормализуем ответ от Google Script
        if result["status"] == "success":
            if "data" in result:
                data = result["data"]
                if isinstance(data, dict):
                    # 🔍 ОТЛАДКА: смотрим, что именно пришло в day_stats
                    print(f"[DEBUG] day_stats raw: {data.get('day_stats')}")
                    print(f"[DEBUG] blood_group_stats raw: {data.get('blood_group_stats')}")
                    
                    # Проверяем, может быть данные лежат в другом поле
                    if not data.get("day_stats") and "days" in data:
                        data["day_stats"] = data["days"]
                    if not data.get("blood_group_stats") and "blood_groups" in data:
                        data["blood_group_stats"] = data["blood_groups"]
                    if not data.get("total_bookings") and "total" in data:
                        data["total_bookings"] = data.get("total", 0)
                    
                    # Заполняем отсутствующие поля
                    if "total_bookings" not in data:
                        data["total_bookings"] = 0
                    if "total_users" not in data:
                        data["total_users"] = 0
                    if "day_stats" not in data:
                        data["day_stats"] = {}
                    if "blood_group_stats" not in data:
                        data["blood_group_stats"] = {}
                    if "most_popular_day" not in data:
                        # Вычисляем из day_stats
                        if data["day_stats"]:
                            try:
                                most_popular = max(data["day_stats"].items(), key=lambda x: x[1])
                                data["most_popular_day"] = most_popular[0]
                            except:
                                data["most_popular_day"] = "нет данных"
                        else:
                            data["most_popular_day"] = "нет данных"
                    if "most_popular_blood_group" not in data:
                        # Вычисляем из blood_group_stats
                        if data["blood_group_stats"]:
                            try:
                                most_popular = max(data["blood_group_stats"].items(), key=lambda x: x[1])
                                data["most_popular_blood_group"] = most_popular[0]
                            except:
                                data["most_popular_blood_group"] = "нет данных"
                        else:
                            data["most_popular_blood_group"] = "нет данных"
                    if "quota_stats" not in data:
                        # Пытаемся получить квоты отдельно
                        quotas_result = get_quotas()
                        if quotas_result["status"] == "success":
                            data["quota_stats"] = quotas_result["data"].get("quotas", {})
                        else:
                            data["quota_stats"] = {}
        
        return result
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def clear_cache() -> dict:
    """Очистить кэш Google Script"""
    if MODE in ["GOOGLE", "HYBRID"]:
        return google_client.call_api("clear_cache", {})
    else:
        return {"status": "success", "data": "В локальном режиме кэш очищается автоматически"}

def force_refresh_cache(user_id: int = None) -> dict:
    """Принудительно обновить кэш данных из Google Таблиц"""
    if MODE in ["GOOGLE", "HYBRID"]:
        print(f"[CACHE] 🔄 Принудительное обновление кэша")
        
        clear_cache_result = clear_cache()
        if clear_cache_result['status'] != 'success':
            print(f"[CACHE] ⚠️ Не удалось очистить кэш: {clear_cache_result.get('data', 'unknown error')}")
        
        if user_id:
            return get_available_dates(user_id, force_refresh=True)
        else:
            test_user_id = 1
            return get_available_dates(test_user_id, force_refresh=True)
    else:
        return {"status": "success", "data": "Локальный режим - кэш не используется"}

# ========== ОГРАНИЧЕНИЕ ЧАСТОТЫ ЗАПРОСОВ ==========
class RateLimiter:
    """Ограничитель частоты запросов"""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests: Dict[int, List[float]] = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> bool:
        """Проверить, можно ли выполнить запрос"""
        now = time.time()
        
        requests = self.user_requests[user_id]
        requests = [req_time for req_time in requests if now - req_time < self.time_window]
        self.user_requests[user_id] = requests
        
        if len(requests) >= self.max_requests:
            return False
        
        requests.append(now)
        return True
    
    def get_wait_time(self, user_id: int) -> float:
        """Получить время ожидания"""
        now = time.time()
        requests = self.user_requests[user_id]
        
        if not requests:
            return 0
        
        oldest_request = min(requests)
        if now - oldest_request >= self.time_window:
            return 0
        
        return self.time_window - (now - oldest_request)

rate_limiter = RateLimiter(max_requests=15, time_window=60)

# ========== СОСТОЯНИЯ БОТА ==========
class Form(StatesGroup):
    waiting_for_blood_group = State()
    waiting_for_date = State()
    waiting_for_time = State()

# ========== ИНЛАЙН-КЛАВИАТУРЫ ==========
def get_blood_group_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора группы крови (8 групп)"""
    builder = InlineKeyboardBuilder()
    
    blood_groups = [
        ("🅰️ A+", "blood_A+"),
        ("🅰️ A-", "blood_A-"),
        ("🅱️ B+", "blood_B+"),
        ("🅱️ B-", "blood_B-"),
        ("🆎 AB+", "blood_AB+"),
        ("🆎 AB-", "blood_AB-"),
        ("🅾️ O+", "blood_O+"),
        ("🅾️ O-", "blood_O-")
    ]
    
    for i in range(0, len(blood_groups), 2):
        row = blood_groups[i:i+2]
        buttons = [InlineKeyboardButton(text=text, callback_data=callback) for text, callback in row]
        builder.row(*buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return builder.as_markup()

def get_dates_keyboard(available_dates: List[dict]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора даты"""
    builder = InlineKeyboardBuilder()
    
    if not available_dates:
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_blood"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        )
        return builder.as_markup()
    
    for date_info in available_dates:
        button_text = f"{date_info['day_of_week']}\n{date_info['display_date']}"
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"date_{date_info['date']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_blood"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return builder.as_markup()

def get_times_keyboard(times_list: List[str], current_step: int = 1, total_steps: int = 3) -> InlineKeyboardMarkup:
    """Клавиатура для выбора времени"""
    builder = InlineKeyboardBuilder()
    
    if not times_list:
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_date"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        )
        return builder.as_markup()
    
    time_buttons = []
    for i, time_str in enumerate(times_list):
        time_buttons.append(
            InlineKeyboardButton(text=f"⏰ {time_str}", callback_data=f"time_{time_str}")
        )
    
    for i in range(0, len(time_buttons), 3):
        builder.row(*time_buttons[i:i+3])
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_date"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    progress = get_progress_bar(current_step, total_steps)
    builder.row(InlineKeyboardButton(text=progress, callback_data="progress_info"))
    
    return builder.as_markup()

def get_progress_bar(current: int, total: int, length: int = 8) -> str:
    """Создает текстовый прогресс-бар"""
    percentage = (current - 1) / (total - 1) if total > 1 else 0
    filled = int(percentage * length)
    empty = length - filled
    
    progress_bar = "🟢" * filled + "⚪" * empty
    return f"{progress_bar} {current}/{total}"

def get_confirm_cancellation_keyboard(date: str, ticket: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения отмены записи"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"cancel_yes_{date}_{ticket}"),
        InlineKeyboardButton(text="❌ Нет, оставить", callback_data="cancel_no")
    )
    
    return builder.as_markup()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Записаться", callback_data="main_record"),
        InlineKeyboardButton(text="🔍 Проверить время", callback_data="main_check")
    )
    builder.row(
        InlineKeyboardButton(text="📖 Мои записи", callback_data="main_mybookings"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="main_stats"),
        InlineKeyboardButton(text="ℹ️ Помощь", callback_data="main_help")
    )
    
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура администратора"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🗑️ Очистить кэш квот", callback_data="admin_clear_cache"),
        InlineKeyboardButton(text="🔄 Обновить кэш", callback_data="admin_refresh_cache")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Проверить квоты", callback_data="admin_show_quotas"),
        InlineKeyboardButton(text="🔄 Сбросить данные", callback_data="admin_reset")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start_command(message: types.Message, state: FSMContext):
    """Команда /start - показывает главное меню"""
    user = message.from_user
    
    if not rate_limiter.is_allowed(user.id):
        wait_time = int(rate_limiter.get_wait_time(user.id))
        await message.answer(
            f"⏳ Слишком много запросов. Пожалуйста, подождите {wait_time} секунд."
        )
        return
    
    await state.clear()
    session_timeout.clear_session(user.id)
    session_timeout.update_activity(user.id)
    
    if MODE in ["GOOGLE", "HYBRID"]:
        print(f"[CACHE] 🔄 Принудительное обновление кэша при старте")
        refresh_result = force_refresh_cache(user.id)
        if refresh_result["status"] == "success":
            print(f"[CACHE] ✅ Кэш успешно обновлен")
        else:
            print(f"[CACHE] ⚠️ Не удалось обновить кэш: {refresh_result.get('data', 'unknown error')}")
    
    greeting_name = user.first_name if user.first_name else "пользователь"
    
    mode_info = {
        "LOCAL": "🔧 Автономный режим",
        "GOOGLE": "🌐 Режим Google Script",
        "HYBRID": "⚡ Гибридный режим"
    }.get(MODE, "❓ Неизвестный режим")
    
    is_admin = user.id in ADMIN_IDS
    admin_text = "\n👑 *Вы администратор* - доступны дополнительные функции" if is_admin else ""
    
    await message.answer(
        f"🎯 *Донорская станция v3.5*\n"
        f"{mode_info}\n\n"
        f"👋 Привет, {greeting_name}!{admin_text}\n\n"
        f"Я помогу вам записаться на донорство крови, "
        f"проверить доступное время или отменить запись.\n\n"
        f"*Новые возможности:*\n"
        f"• 📅 Выбор конкретной даты\n"
        f"• 🩸 8 групп крови\n"
        f"• ⏰ Автоматический поиск доступных дат\n"
        f"• 📊 Статистика из Google Таблиц\n"
        f"• 🔄 Исправлена совместимость с Google Script\n\n"
        f"*Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def process_main_menu(callback: CallbackQuery, state: FSMContext):
    """Обработка главного меню"""
    user = callback.from_user
    
    session_timeout.update_activity(user.id)
    
    if not rate_limiter.is_allowed(user.id):
        wait_time = int(rate_limiter.get_wait_time(user.id))
        await callback.answer(f"⏳ Подождите {wait_time} секунд", show_alert=True)
        return
    
    action = callback.data
    
    if action == "main_record":
        await callback.message.edit_text(
            "🩸 *Выберите вашу группу крови:*\n\n"
            "• 🅰️ A+ - первая положительная\n"
            "• 🅰️ A- - первая отрицательная\n"
            "• 🅱️ B+ - вторая положительная\n"
            "• 🅱️ B- - вторая отрицательная\n"
            "• 🆎 AB+ - третья положительная\n"
            "• 🆎 AB- - третья отрицательная\n"
            "• 🅾️ O+ - четвертая положительная\n"
            "• 🅾️ O- - четвертая отрицательная",
            parse_mode="Markdown",
            reply_markup=get_blood_group_keyboard()
        )
        await state.set_state(Form.waiting_for_blood_group)
        await state.update_data(is_check_command=False)
    
    elif action == "main_check":
        await callback.message.edit_text(
            "🔍 *Проверка доступного времени*\n\n"
            "Выберите вашу группу крови:",
            parse_mode="Markdown",
            reply_markup=get_blood_group_keyboard()
        )
        await state.set_state(Form.waiting_for_blood_group)
        await state.update_data(is_check_command=True)
    
    elif action == "main_mybookings":
        await show_my_bookings(callback.message, user)
    
    elif action == "main_stats":
        await show_stats(callback.message)
    
    elif action == "main_help":
        await help_command(callback.message)
    
    await callback.answer()

async def process_blood_group(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора группы крови"""
    user = callback.from_user
    
    session_timeout.update_activity(user.id)
    
    if callback.data == "cancel":
        await cancel_command(callback.message, state)
        await callback.answer()
        return
    
    if callback.data == "main_menu":
        await show_main_menu_from_callback(callback)
        await state.clear()
        await callback.answer()
        return
    
    if callback.data == "back_to_blood":
        await callback.answer()
        return
    
    if not callback.data.startswith("blood_"):
        await callback.answer("Пожалуйста, выберите группу крови", show_alert=True)
        return
    
    blood_group = callback.data[6:]
    
    await state.update_data(blood_group=blood_group)
    
    response = get_available_dates(user.id)
    
    if response['status'] == 'error':
        await callback.message.edit_text(
            f"❌ *Ошибка получения дат:* {response['data']}\n\n"
            f"Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    available_dates = response['data']['available_dates']
    
    if not available_dates:
        await callback.message.edit_text(
            "😔 *Нет доступных дат для записи*\n\n"
            "К сожалению, на ближайшие дни нет свободных мест.\n"
            "Попробуйте позже или обратитесь в регистратуру.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    user_data = await state.get_data()
    is_check = user_data.get('is_check_command', False)
    
    action_text = "проверки" if is_check else "записи"
    
    dates_text = ""
    for i, date_info in enumerate(available_dates[:6]):
        dates_text += f"• *{date_info['day_of_week']}* - {date_info['display_date']}\n"
    
    await callback.message.edit_text(
        f"📅 *Выберите дату для {action_text}:*\n\n"
        f"🩸 Выбранная группа крови: *{blood_group}*\n\n"
        f"*Доступные даты:*\n{dates_text}",
        parse_mode="Markdown",
        reply_markup=get_dates_keyboard(available_dates)
    )
    
    await state.set_state(Form.waiting_for_date)
    await callback.answer(f"Выбрана группа крови {blood_group}")

async def process_date(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора даты"""
    user = callback.from_user
    
    session_timeout.update_activity(user.id)
    
    if callback.data == "cancel":
        await cancel_command(callback.message, state)
        await callback.answer()
        return
    
    if callback.data == "back_to_blood":
        await callback.message.edit_text(
            "🩸 *Выберите вашу группу крови:*",
            parse_mode="Markdown",
            reply_markup=get_blood_group_keyboard()
        )
        await state.set_state(Form.waiting_for_blood_group)
        await callback.answer()
        return
    
    if not callback.data.startswith("date_"):
        await callback.answer("Пожалуйста, выберите дату", show_alert=True)
        return
    
    selected_date = callback.data[5:]
    
    user_data = await state.get_data()
    blood_group = user_data.get('blood_group')
    
    if not blood_group:
        await callback.message.edit_text(
            "❌ *Ошибка:* Группа крови не выбрана\n\n"
            "Пожалуйста, начните запись заново.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    await state.update_data(selected_date=selected_date)
    
    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        display_date = date_obj.strftime("%d.%m.%Y")
        
        days_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        day_of_week = days_ru[date_obj.weekday()]
        
    except ValueError:
        display_date = selected_date
        day_of_week = "неизвестно"
    
    response = get_free_times(selected_date, blood_group)
    
    if response['status'] == 'error':
        await callback.message.edit_text(
            f"❌ *Ошибка:* {response['data']}\n\n"
            f"Попробуйте выбрать другую дату.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return
    
    times = response['data']['times']
    quota = response['data']['quota']
    
    is_check = user_data.get('is_check_command', False)
    
    if not times:
        if is_check:
            await callback.message.edit_text(
                f"📅 *На {display_date} ({day_of_week}) для группы {blood_group} все квоты заняты.*\n"
                f"📊 Осталось мест: {quota}\n\n"
                f"Попробуйте выбрать другую дату.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            # Получаем актуальный список дат
            dates_response = get_available_dates(user.id)
            if dates_response['status'] == 'success':
                available_dates = dates_response['data']['available_dates']
            else:
                available_dates = []
                
            await callback.message.edit_text(
                f"❌ *На {display_date} ({day_of_week}) для группы {blood_group} все квоты заняты.*\n"
                f"📊 Осталось мест: {quota}\n\n"
                f"*Выберите другую дату:*",
                parse_mode="Markdown",
                reply_markup=get_dates_keyboard(available_dates)
            )
        await state.clear() if is_check else None
        await callback.answer()
        return
    
    if is_check:
        time_groups = {}
        for t in times:
            hour = t.split(':')[0]
            minute = t.split(':')[1]
            
            if hour not in time_groups:
                time_groups[hour] = []
            time_groups[hour].append(minute)
        
        sorted_hours = sorted(time_groups.keys())
        
        grouped_text = ""
        for hour in sorted_hours:
            minutes = time_groups[hour]
            minutes_sorted = sorted(minutes)
            minutes_str = ", ".join(minutes_sorted)
            grouped_text += f"• {hour}:{minutes_str}\n"
        
        time_count = len(times)
        if time_count == 1:
            slot_word = "слот"
        elif 2 <= time_count <= 4:
            slot_word = "слота"
        else:
            slot_word = "слотов"
        
        await callback.message.edit_text(
            f"📅 *Доступное время на {display_date}:*\n"
            f"📋 {day_of_week}\n"
            f"🩸 Группа крови: {blood_group}\n"
            f"📊 Свободно {time_count} {slot_word} из {quota}\n\n"
            f"*Временные слоты:*\n{grouped_text}\n"
            f"Для записи нажмите 'Записаться' в главном меню.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
    else:
        current_step = 2
        total_steps = 3
        
        await callback.message.edit_text(
            f"✅ *Доступное время на {display_date}:*\n"
            f"📋 {day_of_week}\n"
            f"🩸 Группа крови: {blood_group}\n"
            f"📊 Свободных мест: {quota}\n\n"
            f"*Выберите удобное время:*",
            parse_mode="Markdown",
            reply_markup=get_times_keyboard(times, current_step, total_steps)
        )
        await state.set_state(Form.waiting_for_time)
    
    await callback.answer(f"Выбрана дата {display_date}")

async def process_time(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора времени"""
    user = callback.from_user
    
    session_timeout.update_activity(user.id)
    
    if callback.data == "cancel":
        await cancel_command(callback.message, state)
        await callback.answer()
        return
    
    if callback.data == "back_to_date":
        user_data = await state.get_data()
        blood_group = user_data.get('blood_group')
        
        # Получаем актуальный список дат
        dates_response = get_available_dates(user.id, force_refresh=True)
        if dates_response['status'] == 'success':
            available_dates = dates_response['data']['available_dates']
        else:
            available_dates = []
        
        dates_text = ""
        for i, date_info in enumerate(available_dates[:6]):
            dates_text += f"• *{date_info['day_of_week']}* - {date_info['display_date']}\n"
        
        await callback.message.edit_text(
            f"📅 *Выберите дату:*\n\n"
            f"🩸 Группа крови: *{blood_group}*\n\n"
            f"*Доступные даты:*\n{dates_text}",
            parse_mode="Markdown",
            reply_markup=get_dates_keyboard(available_dates)
        )
        await state.set_state(Form.waiting_for_date)
        await callback.answer()
        return
    
    if callback.data == "progress_info":
        await callback.answer("Прогресс записи: выбор времени", show_alert=True)
        return
    
    if not callback.data.startswith("time_"):
        await callback.answer("Пожалуйста, выберите время", show_alert=True)
        return
    
    selected_time = callback.data.split("_", 1)[1]
    user_data = await state.get_data()
    
    selected_date = user_data.get('selected_date')
    blood_group = user_data.get('blood_group')
    
    if not selected_date or not blood_group:
        await callback.message.edit_text(
            "❌ *Ошибка:* Отсутствуют данные записи\n\n"
            "Пожалуйста, начните запись заново.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        display_date = date_obj.strftime("%d.%m.%Y")
    except ValueError:
        display_date = selected_date
    
    check_response = check_existing(selected_date, user.id)
    
    if check_response['status'] == 'error':
        await callback.message.edit_text(
            f"❌ *Ошибка проверки:* {check_response['data']}\n\n"
            f"Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    if check_response['data']['exists']:
        existing = check_response['data']
        await callback.message.edit_text(
            f"⚠️ *У вас уже есть запись на {display_date}!*\n\n"
            f"🎫 Ваш талон: {existing['ticket']}\n"
            f"⏰ Время: {existing['time']}\n\n"
            f"📌 *Одна запись в день на пользователя.*\n"
            f"Для отмены перейдите в 'Мои записи'.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return
    
    # ПЕРЕД РЕГИСТРАЦИЕЙ получаем актуальные данные о квотах
    times_response = get_free_times(selected_date, blood_group)
    if times_response['status'] == 'success':
        quota_before = times_response['data'].get('quota', 0)
        print(f"[BOOKING] 📊 Квота до записи: {quota_before} для {selected_date} {blood_group}")
    
    response = register(
        selected_date,
        blood_group,
        selected_time,
        user.id
    )
    
    if response['status'] == 'error':
        # Получаем актуальные времена для повторного выбора
        times_response = get_free_times(selected_date, blood_group)
        if times_response['status'] == 'success':
            times = times_response['data']['times']
        else:
            times = []
            
        await callback.message.edit_text(
            f"❌ *Ошибка регистрации:* {response['data']}\n\n"
            f"Попробуйте выбрать другое время.",
            parse_mode="Markdown",
            reply_markup=get_times_keyboard(times, 2, 3)
        )
        await callback.answer()
        return
    
    ticket_data = response['data']
    
    # ПОСЛЕ РЕГИСТРАЦИИ принудительно обновляем кэш
    get_free_times(selected_date, blood_group)  # force_refresh уже внутри
    
    # ПРОВЕРЯЕМ реальный остаток мест
    check_after = get_free_times(selected_date, blood_group)
    if check_after['status'] == 'success':
        real_quota = check_after['data'].get('quota', 0)
        print(f"[BOOKING] 📊 Квота после записи: {real_quota} для {selected_date} {blood_group}")
        # Используем реальные данные
        ticket_data['quota_remaining'] = real_quota
    
    ticket_text = (
        "🎫 *ВАШ ТАЛОН НА ДОНОРСТВО*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🎫 Номер: *{ticket_data['ticket']}*\n"
        f"• 📅 Дата: *{display_date}*\n"
        f"• 📋 День: *{ticket_data['day']}*\n"
        f"• ⏰ Время: *{ticket_data['time']}*\n"
        f"• 🩸 Группа крови: *{ticket_data['blood_group']}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Осталось мест в этот день: *{ticket_data['quota_remaining']}*\n\n"
        f"👤 ID пользователя: `{user.id}`\n\n"
        "⚠️ *Пожалуйста, приходите за 10 минут до назначенного времени.*\n"
        "📌 *Одна запись в день на пользователя.*"
    )
    
    await callback.message.edit_text(
        ticket_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    
    await state.clear()
    await callback.answer("✅ Запись успешно оформлена!")


def force_refresh_quotas(date: str, blood_group: str) -> dict:
    """Принудительно обновить квоты для конкретной даты и группы крови"""
    if MODE in ["GOOGLE", "HYBRID"]:
        # Очищаем кэш для этого конкретного запроса
        cache_key = f"get_free_times_None_{json.dumps({'date': date, 'blood_group': blood_group}, sort_keys=True)}"
        if cache_key in google_client.cache:
            del google_client.cache[cache_key]
            del google_client.cache_time[cache_key]
        
        # Делаем запрос с force_refresh
        return google_client.call_api("get_free_times", {"date": date, "blood_group": blood_group}, force_refresh=True)
    return {"status": "error", "data": "Не в режиме Google"}


# ========== ФУНКЦИИ КОМАНД ==========
async def cancel_command(message: types.Message, state: FSMContext):
    """Команда /cancel - отмена текущего диалога"""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "ℹ️ *Нет активного диалога для отмены.*\n"
            "Используйте кнопки ниже для навигации:",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    await state.clear()
    
    await message.answer(
        "✅ *Текущий диалог отменен.*\n"
        "Все данные очищены.\n\n"
        "*Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def help_command(message: types.Message):
    """Команда /help"""
    help_text = (
        "📋 *Помощь по боту v3.5:*\n\n"
        "*Основные функции:*\n"
        "• 📋 Записаться на донорство\n"
        "• 🔍 Проверить доступное время\n"
        "• 📖 Посмотреть свои записи\n"
        "• 📊 Показать статистику\n"
        "• ❌ Отменить свою запись\n\n"
        "*Новые возможности:*\n"
        "📅 *Выбор конкретных дат*\n"
        "🩸 *8 групп крови*\n"
        "⚡ *Автоматический поиск дат*\n"
        "⏰ *Таймаут сессии* 10 минут\n"
        "📊 *Статистика из Google Таблиц*\n"
        "🔄 *Исправлена совместимость с Google Script*\n\n"
        "*Правила:*\n"
        "📌 Одна запись в день на пользователя\n"
        "📅 Запись на ближайшие доступные даты\n"
        "👥 Квоты разделены по группам крови\n\n"
        "*Режимы работы:*\n"
        "🔧 *LOCAL* - автономный режим\n"
        "🌐 *GOOGLE* - данные в Google Таблицах\n"
        "⚡ *HYBRID* - автоматическое переключение\n\n"
        "*Администраторские функции:*\n"
        "🔄 Обновить кэш из Google Таблиц\n"
        "🗑️ Очистить кэш квот\n"
        "📊 Проверить квоты\n"
        "🔄 Сбросить все данные\n\n"
        "По вопросам обращайтесь к администратору."
    )
    
    await message.answer(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def mybookings_command(message: types.Message):
    """Команда /mybookings - посмотреть мои записи"""
    user = message.from_user
    await show_my_bookings(message, user)

async def show_my_bookings(message: types.Message, user: types.User):
    """Показать записи пользователя"""
    response = get_user_bookings(user.id)
    
    if response['status'] == 'error':
        await message.answer(
            f"❌ *Ошибка получения записей:* {response['data']}",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    bookings = response['data']['bookings']
    
    if not bookings:
        await message.answer(
            f"📋 *Ваши записи*\n\n"
            f"👤 Пользователь: {user.full_name or 'ID: ' + str(user.id)}\n"
            f"🔢 Ваш ID: `{user.id}`\n\n"
            f"*У вас нет активных записей.*\n\n"
            f"Для записи нажмите кнопку ниже:",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        builder = InlineKeyboardBuilder()
        
        bookings_text = ""
        for i, booking in enumerate(bookings):
            try:
                date_obj = datetime.strptime(booking['date'], "%Y-%m-%d")
                display_date = date_obj.strftime("%d.%m.%Y")
            except ValueError:
                display_date = booking['date']
            
            bookings_text += f"• *{display_date}* ({booking['day']}): {booking['time']} (талон: {booking['ticket']}, группа: {booking['blood_group']})\n"
            
            builder.row(
                InlineKeyboardButton(
                    text=f"❌ Отменить запись на {display_date}",
                    callback_data=f"cancel_ask_{booking['date']}_{booking['ticket']}"
                )
            )
        
        builder.row(
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
        )
        
        await message.answer(
            f"📋 *Ваши записи*\n\n"
            f"👤 Пользователь: {user.full_name or 'ID: ' + str(user.id)}\n"
            f"🔢 Ваш ID: `{user.id}`\n\n"
            f"*Активные записи:*\n{bookings_text}\n"
            f"📌 *Одна запись в день на пользователя.*\n"
            f"ℹ️ *Для отмены записи нажмите соответствующую кнопку ниже.*",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )

async def stats_command(message: types.Message):
    """Команда /stats - показать статистику"""
    await show_stats(message)

async def show_stats(message: types.Message):
    """Показать статистику"""
    stats_response = get_stats()
    
    if stats_response['status'] == 'error':
        await message.answer(
            f"❌ *Ошибка получения статистики:* {stats_response['data']}",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    stats_data = stats_response['data']
    
    # Безопасно получаем данные со значениями по умолчанию
    total_bookings = stats_data.get("total_bookings", 0)
    total_users = stats_data.get("total_users", 0)
    most_popular_day = stats_data.get("most_popular_day", "нет данных")
    most_popular_blood = stats_data.get("most_popular_blood_group", "нет данных")
    
    day_stats = stats_data.get("day_stats", {})
    blood_group_stats = stats_data.get("blood_group_stats", {})
    quota_stats = stats_data.get("quota_stats", {})
    
    # Форматируем статистику по дням
    day_stats_text = ""
    if isinstance(day_stats, dict):
        valid_days = []
        for day, count in day_stats.items():
            if isinstance(count, (int, float)) and count > 0:
                valid_days.append((day, count))
        
        if valid_days:
            sorted_days = sorted(valid_days, key=lambda x: x[1], reverse=True)[:5]
            for day, count in sorted_days:
                day_stats_text += f"• *{day}*: {count} зап.\n"
    
    if not day_stats_text:
        day_stats_text = "• Нет данных\n"
    
    # Форматируем статистику по группам крови
    blood_stats_text = ""
    if isinstance(blood_group_stats, dict):
        valid_blood = []
        for bg, count in blood_group_stats.items():
            if isinstance(count, (int, float)) and count > 0:
                valid_blood.append((bg, count))
        
        if valid_blood:
            sorted_bg = sorted(valid_blood, key=lambda x: x[1], reverse=True)
            for bg, count in sorted_bg:
                blood_stats_text += f"• *{bg}*: {count} зап.\n"
    
    if not blood_stats_text:
        blood_stats_text = "• Нет данных\n"
    
    # Форматируем информацию о квотах
    quota_info = ""
    if isinstance(quota_stats, dict):
        total_quota = quota_stats.get('totalQuota', 0)
        total_used = quota_stats.get('totalUsed', 0)
        remaining = quota_stats.get('remaining', total_quota - total_used)
        
        quota_info = f"📊 *Общая квота:* {total_quota} мест\n"
        quota_info += f"✅ *Использовано:* {total_used} мест\n"
        quota_info += f"⏳ *Осталось:* {remaining} мест\n\n"
    
    mode_info = {
        "LOCAL": "🔧 *АВТОНОМНЫЙ РЕЖИМ*",
        "GOOGLE": "🌐 *РЕЖИМ GOOGLE SCRIPT*",
        "HYBRID": "⚡ *ГИБРИДНЫЙ РЕЖИМ*"
    }.get(MODE, "")
    
    stats_text = (
        f"📊 *Статистика донорской станции*\n\n"
        f"👥 *Всего пользователей:* {total_users}\n"
        f"📋 *Всего записей:* {total_bookings}\n"
        f"📅 *Популярный день:* {most_popular_day}\n"
        f"🩸 *Популярная группа:* {most_popular_blood}\n\n"
        f"{quota_info}"
        f"*Записи по дням:*\n{day_stats_text}"
        f"*Записи по группам крови:*\n{blood_stats_text}"
        f"{mode_info}"
    )
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    if message.from_user.id in ADMIN_IDS:
        builder.row(
            InlineKeyboardButton(text="🗑️ Очистить кэш", callback_data="admin_clear_cache"),
            InlineKeyboardButton(text="🔄 Обновить кэш", callback_data="admin_refresh_cache")
        )
        builder.row(
            InlineKeyboardButton(text="📊 Проверить квоты", callback_data="admin_show_quotas"),
            InlineKeyboardButton(text="🔄 Сбросить данные", callback_data="admin_reset")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
    )
    
    await message.answer(
        stats_text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

async def show_quotas(message: types.Message):
    """Показать информацию о квотах (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ *У вас нет прав для просмотра квот.*",
            parse_mode="Markdown"
        )
        return
    
    quotas_response = get_quotas()
    
    if quotas_response['status'] == 'error':
        await message.answer(
            f"❌ *Ошибка получения квот:* {quotas_response['data']}",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        return
    
    quotas_data = quotas_response['data']
    
    # Проверяем структуру ответа
    if isinstance(quotas_data, dict) and 'quotas' in quotas_data:
        quotas = quotas_data['quotas']
        message_text = quotas_data.get('message', 'Информация о квотах')
    else:
        await message.answer(
            f"📊 *Информация о квотах*\n\n{quotas_data}",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # Получаем данные с безопасными значениями по умолчанию
    total_quota = quotas.get('totalQuota', 0)
    total_used = quotas.get('totalUsed', 0)
    remaining = quotas.get('remaining', total_quota - total_used)
    by_day = quotas.get('byDay', {})
    
    text = f"📊 *КВОТЫ ДОНОРСКОЙ СТАНЦИИ*\n\n"
    text += f"📋 *Всего квот:* {total_quota}\n"
    text += f"✅ *Использовано:* {total_used}\n"
    text += f"⏳ *Осталось:* {remaining}\n\n"
    
    if by_day:
        text += f"*Детали по дням:*\n"
        for day, day_data in by_day.items():
            day_total = day_data.get('total', 0)
            day_used = day_data.get('used', 0)
            day_remaining = day_data.get('remaining', day_total - day_used)
            text += f"\n📅 *{day}*:\n"
            text += f"  Всего: {day_total}, Использовано: {day_used}, Осталось: {day_remaining}\n"
            
            day_quotas = day_data.get('quotas', {})
            if day_quotas:
                # Форматируем квоты по группам крови в строку
                quotas_list = []
                for bg, q in day_quotas.items():
                    if q > 0:  # Показываем только группы с ненулевыми квотами
                        quotas_list.append(f"{bg}: {q}")
                if quotas_list:
                    text += f"  Квоты по группам: {', '.join(quotas_list)}\n"
    else:
        text += f"\n*Детали по дням:*\n• Нет данных\n"
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh_cache"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_stats")
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

async def reset_command(message: types.Message):
    """Команда /reset - сбросить все данные (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ *У вас нет прав для выполнения этой команды.*",
            parse_mode="Markdown"
        )
        return
    
    # Очищаем Google Script кэш
    if MODE in ["GOOGLE", "HYBRID"]:
        clear_cache_result = clear_cache()
        if clear_cache_result['status'] == 'success':
            print(f"[RESET] ✅ Кэш Google Script очищен")
        else:
            print(f"[RESET] ⚠️ Ошибка очистки кэша: {clear_cache_result.get('data')}")
    
    # Сбрасываем локальные данные
    local_storage.reset_data()
    
    # Принудительно обновляем кэш
    if MODE in ["GOOGLE", "HYBRID"]:
        force_refresh_cache(message.from_user.id)
    
    await message.answer(
        "✅ *Все данные успешно сброшены!*\n\n"
        "Тестовые данные восстановлены.\n"
        "Кэш Google Script очищен.\n"
        "Все пользовательские записи удалены.\n\n"
        "Используйте /start для начала работы.",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )

async def clear_cache_command(message: types.Message):
    """Команда /clearcache - очистить кэш квот (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ *У вас нет прав для выполнения этой команды.*",
            parse_mode="Markdown"
        )
        return
    
    result = clear_cache()
    
    if result['status'] == 'success':
        await message.answer(
            "✅ *Кэш квот успешно очищен!*\n\n"
            "Теперь будут загружены свежие данные из Google Таблиц.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            f"❌ *Ошибка очистки кэша:* {result['data']}\n\n"
            f"Проверьте подключение к Google Script.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

async def refresh_cache_command(message: types.Message):
    """Команда /refresh - обновить кэш из Google Таблиц (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ *У вас нет прав для выполнения этой команды.*",
            parse_mode="Markdown"
        )
        return
    
    if MODE in ["GOOGLE", "HYBRID"]:
        msg = await message.answer("🔄 *Обновление кэша из Google Таблиц...*", parse_mode="Markdown")
        
        result = force_refresh_cache(message.from_user.id)
        
        if result["status"] == "success":
            await msg.edit_text(
                "✅ *Кэш успешно обновлен из Google Таблиц!*\n\n"
                "Теперь отображаются актуальные данные.\n"
                f"Доступно дат: {result['data'].get('count', 0)}",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
        else:
            await msg.edit_text(
                f"❌ *Ошибка обновления кэша:* {result['data']}",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
    else:
        await message.answer(
            "ℹ️ *В локальном режиме кэш не используется.*\n"
            "Данные берутся напрямую из памяти бота.",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

async def process_cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены записи и админских действий"""
    try:
        session_timeout.update_activity(callback.from_user.id)
        
        if callback.data == "cancel_no":
            await callback.message.edit_text(
                "✅ *Отмена записи отменена.*\n\n"
                "Ваша запись сохранена.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
            await callback.answer()
            return
        
        if callback.data.startswith("cancel_yes_"):
            parts = callback.data.split("_")
            if len(parts) >= 4:
                date = parts[2]
                ticket = "_".join(parts[3:])
                
                response = cancel_booking(
                    date,
                    ticket,
                    callback.from_user.id
                )
                
                if response['status'] == 'success':
                    try:
                        date_obj = datetime.strptime(date, "%Y-%m-%d")
                        display_date = date_obj.strftime("%d.%m.%Y")
                    except ValueError:
                        display_date = date
                    
                    await callback.message.edit_text(
                        f"✅ *Запись успешно отменена!*\n\n"
                        f"📅 Дата: *{display_date}*\n"
                        f"🎫 Талон: *{ticket}*\n\n"
                        f"Теперь вы можете записаться на другое время.",
                        parse_mode="Markdown",
                        reply_markup=get_main_menu_keyboard()
                    )
                else:
                    await callback.message.edit_text(
                        f"❌ *Ошибка отмены записи:* {response['data']}\n\n"
                        f"Попробуйте позже или обратитесь к администратору.",
                        parse_mode="Markdown",
                        reply_markup=get_main_menu_keyboard()
                    )
            else:
                await callback.message.edit_text(
                    "❌ *Ошибка обработки запроса на отмену.*",
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard()
                )
            
            await callback.answer()
            return
        
        if callback.data.startswith("cancel_ask_"):
            parts = callback.data.split("_")
            if len(parts) >= 4:
                date = parts[2]
                ticket = "_".join(parts[3:])
                
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    display_date = date_obj.strftime("%d.%m.%Y")
                except ValueError:
                    display_date = date
                
                await callback.message.edit_text(
                    f"⚠️ *Подтверждение отмены записи*\n\n"
                    f"📅 Дата: *{display_date}*\n"
                    f"🎫 Номер талона: *{ticket}*\n\n"
                    f"Вы уверены, что хотите отменить эту запись?",
                    parse_mode="Markdown",
                    reply_markup=get_confirm_cancellation_keyboard(date, ticket)
                )
            
            await callback.answer()
            return
        
        if callback.data == "main_menu":
            await show_main_menu_from_callback(callback)
            await state.clear()
            await callback.answer()
            return
        
        if callback.data == "admin_show_quotas":
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ У вас нет прав для этой операции", show_alert=True)
                return
            
            quotas_response = get_quotas()
            
            if quotas_response['status'] == 'error':
                await callback.message.edit_text(
                    f"❌ *Ошибка получения квот:* {quotas_response['data']}",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
                await callback.answer()
                return
            
            quotas_data = quotas_response['data']
            
            if isinstance(quotas_data, dict) and 'quotas' in quotas_data:
                quotas = quotas_data['quotas']
                message_text = quotas_data.get('message', 'Информация о квотах')
            else:
                await callback.message.edit_text(
                    f"📊 *Информация о квотах*\n\n{quotas_data}",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
                await callback.answer()
                return
            
            total_quota = quotas.get('totalQuota', 0)
            total_used = quotas.get('totalUsed', 0)
            remaining = quotas.get('remaining', total_quota - total_used)
            by_day = quotas.get('byDay', {})
            
            text = f"📊 *КВОТЫ ДОНОРСКОЙ СТАНЦИИ*\n\n"
            text += f"📋 *Всего квот:* {total_quota}\n"
            text += f"✅ *Использовано:* {total_used}\n"
            text += f"⏳ *Осталось:* {remaining}\n\n"
            text += f"*Детали по дням:*\n"
            
            for day, day_data in by_day.items():
                day_total = day_data.get('total', 0)
                day_used = day_data.get('used', 0)
                day_remaining = day_data.get('remaining', day_total - day_used)
                text += f"\n📅 *{day}*:\n"
                text += f"  Всего: {day_total}, Использовано: {day_used}, Осталось: {day_remaining}\n"
                
                day_quotas = day_data.get('quotas', {})
                if day_quotas:
                    quotas_text = ", ".join([f"{bg}: {q}" for bg, q in day_quotas.items()])
                    text += f"  Квоты по группам: {quotas_text}\n"
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh_cache"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_stats")
            )
            
            await callback.message.edit_text(
                text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            await callback.answer()
            return
        
        if callback.data == "admin_reset":
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ У вас нет прав для этой операции", show_alert=True)
                return
            
            local_storage.reset_data()
            await callback.message.edit_text(
                "✅ *Все данные успешно сброшены!*\n\n"
                "Тестовые данные восстановлены.\n"
                "Все пользовательские записи удалены.",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            await callback.answer()
            return
        
        if callback.data == "admin_clear_cache":
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ У вас нет прав для этой операции", show_alert=True)
                return
            
            result = clear_cache()
            
            if result['status'] == 'success':
                await callback.message.edit_text(
                    "✅ *Кэш квот успешно очищен!*\n\n"
                    "Теперь будут загружены свежие данные из Google Таблиц.",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await callback.message.edit_text(
                    f"❌ *Ошибка очистки кэша:* {result['data']}\n\n"
                    f"Проверьте подключение к Google Script.",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
            await callback.answer()
            return
        
        if callback.data == "admin_refresh_cache":
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ У вас нет прав для этой операции", show_alert=True)
                return
            
            result = force_refresh_cache(callback.from_user.id)
            
            if result['status'] == 'success':
                await callback.message.edit_text(
                    "✅ *Кэш успешно обновлен из Google Таблиц!*\n\n"
                    "Теперь отображаются актуальные данные.\n"
                    f"Доступно дат: {result['data'].get('count', 0)}",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await callback.message.edit_text(
                    f"❌ *Ошибка обновления кэша:* {result['data']}",
                    parse_mode="Markdown",
                    reply_markup=get_admin_keyboard()
                )
            await callback.answer()
            return
        
    except Exception as e:
        print(f"❌ Ошибка в обработке отмены: {e}")
        await callback.message.edit_text(
            "❌ *Произошла ошибка при обработке запроса.*\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()

async def show_main_menu_from_callback(callback: CallbackQuery):
    """Показать главное меню из callback"""
    user = callback.from_user
    greeting_name = user.first_name if user.first_name else "пользователь"
    
    session_timeout.update_activity(user.id)
    
    mode_info = {
        "LOCAL": "🔧 Автономный режим",
        "GOOGLE": "🌐 Режим Google Script",
        "HYBRID": "⚡ Гибридный режим"
    }.get(MODE, "❓ Неизвестный режим")
    
    is_admin = user.id in ADMIN_IDS
    admin_text = "\n👑 *Вы администратор* - доступны дополнительные функции" if is_admin else ""
    
    await callback.message.edit_text(
        f"🎯 *Донорская станция v3.5*\n"
        f"{mode_info}\n\n"
        f"👋 Привет, {greeting_name}!{admin_text}\n\n"
        f"Я помогу вам записаться на донорство крови, "
        f"проверить доступное время или отменить запись.\n\n"
        f"*Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def process_main_menu_button(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'В главное меню'"""
    if callback.data == "main_menu":
        session_timeout.update_activity(callback.from_user.id)
        await show_main_menu_from_callback(callback)
        await state.clear()
        await callback.answer("Главное меню")

# ========== ЗАПУСК БОТА ==========
async def main():
    """Основная функция запуска бота"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    import ssl
    import aiohttp
    from aiogram.client.session.aiohttp import AiohttpSession
    
    print("=" * 60)
    print("🚀 ЗАПУСК ДОНОРСКОГО БОТА v3.5")
    print("=" * 60)
    
    if MODE in ["GOOGLE", "HYBRID"]:
        print("🔗 Тестирование соединения с Google Script...")
        test_result = google_client.test_connection()
        
        if test_result["status"] == "success":
            print(f"✅ Google Script доступен: {test_result['data'].get('message', 'OK')}")
        else:
            print(f"⚠️ Google Script недоступен: {test_result['data']}")
            
            if MODE == "GOOGLE":
                print("❌ Режим GOOGLE выбран, но сервис недоступен!")
                print("🔄 Переключите MODE на 'HYBRID' или 'LOCAL'")
                return
            elif MODE == "HYBRID":
                print("🔄 Гибридный режим: будет использоваться локальное хранилище")
    
    print(f"⚡ РЕЖИМ РАБОТЫ: {MODE}")
    print(f"⏰ ТАЙМАУТ СЕССИИ: {SESSION_TIMEOUT} секунд")
    
    if MODE == "LOCAL":
        print("💾 Данные хранятся в памяти бота")
        print("⚠️ Внимание: При перезапуске бота данные будут сброшены!")
    elif MODE == "GOOGLE":
        print("🌐 Данные хранятся в Google Таблицах")
        print(f"📊 URL: {GOOGLE_SCRIPT_URL}")
        print("🔄 Кэш автоматически обновляется при команде /start")
        print("✅ Исправлена совместимость с Google Script")
    elif MODE == "HYBRID":
        print("⚡ Гибридный режим: Google Script + локальное хранилище")
        print("🔄 Автоматическое переключение при ошибках")
        print("✅ Исправлена совместимость с Google Script")
    
    print("=" * 60)
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    aiohttp_session = aiohttp.ClientSession(connector=connector)
    
    session = AiohttpSession()
    session._session = aiohttp_session
    
    bot = Bot(token=TOKEN, session=session)
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.update.middleware(timeout_middleware)
    
    dp.message.register(start_command, Command("start"))
    dp.message.register(cancel_command, Command("cancel"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(mybookings_command, Command("mybookings"))
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(reset_command, Command("reset"))
    dp.message.register(clear_cache_command, Command("clearcache"))
    dp.message.register(refresh_cache_command, Command("refresh"))
    
    dp.callback_query.register(process_main_menu_button, F.data == "main_menu")
    dp.callback_query.register(process_main_menu, F.data.startswith("main_"))
    dp.callback_query.register(process_blood_group, Form.waiting_for_blood_group)
    dp.callback_query.register(process_date, Form.waiting_for_date)
    dp.callback_query.register(process_time, Form.waiting_for_time)
    dp.callback_query.register(process_cancel_booking)
    
    print("✅ Бот инициализирован и готов к работе!")
    print("📱 Отправьте /start в Telegram для начала работы")
    print("=" * 60)
    print("Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        await aiohttp_session.close()
        print("✅ Сессии закрыты")

if __name__ == "__main__":
    asyncio.run(main())
    

