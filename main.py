"""
🎯 БОТ ДЛЯ ЗАПИСИ НА ДОНОРСТВО КРОВИ
Версия: 3.1 (С поддержкой дат, 8 групп крови и очисткой кэша)
Автор: AI Assistant
Дата: 2024

Особенности:
✅ Поддержка выбора конкретных дат вместо дней недели
✅ 8 групп крови вместо 4
✅ Таймаут сессии 10 минут
✅ Двухстрочные кнопки с датами
✅ Автоматическое обновление доступных дат
✅ Кэширование данных
✅ Очистка кэша через Google Script
✅ ИСПРАВЛЕНА ОШИБКА ТАЙМАУТА СЕССИИ
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

# === ДОБАВЬТЕ ЭТО ===
#import os
#os.environ['HTTP_PROXY'] = '10.1.1.10:3128'
#os.environ['HTTPS_PROXY'] = '10.1.1.10:3128'

# Режим работы (LOCAL, GOOGLE, HYBRID)
MODE = "LOCAL"

# URL вашего Google Apps Script (ЗАМЕНИТЕ НА СВОЙ!)
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbznf0GFFr0HCZgB-_jsSXAY19iwwg-Y_q42T4MPzQVPw3iAufAfwo-ZNKEr3_7HKjPGDQ/exec"

# ID администраторов (для команды /reset)
ADMIN_IDS = [5097581039]  # Замените на ваш Telegram ID

# Таймаут сессии в секундах (10 минут)
SESSION_TIMEOUT = 600

# ========== КЛИЕНТ GOOGLE SCRIPT ==========
class GoogleScriptClient:
    """Клиент для работы с Google Apps Script"""
    
    def __init__(self, script_url: str):
        self.script_url = script_url
        self.session = requests.Session()
        self.session.verify = False  # Отключаем SSL проверку для корпоративных прокси
        self.timeout = 15
        self.cache = {}  # Простой кэш в памяти
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
    
    def call_api(self, action: str, data: dict = None, user_id: int = None) -> dict:
        """Вызвать API Google Script с кэшированием"""
        if data is None:
            data = {}
            
        cache_key = f"{action}_{user_id}_{json.dumps(data, sort_keys=True)}"
        
        # Проверяем кэш для некоторых действий
        if action in ["get_available_dates"]:
            if cache_key in self.cache:
                cache_age = time.time() - self.cache_time.get(cache_key, 0)
                if cache_age < 300:  # Кэш на 5 минут
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
                    
                    # Сохраняем в кэш
                    if action in ["get_available_dates"]:
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

# ========== ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (ОБНОВЛЕНО) ==========
class LocalStorage:
    """Локальное хранилище данных для автономного режима"""
    
    def __init__(self):
        self.reset_data()
        print("[LOCAL] 💾 Локальное хранилище инициализировано (v3.1)")
        
    def reset_data(self):
        """Сбросить все данные"""
        self.bookings = {}  # {user_id: {date: {ticket, time, blood_group, day}}}
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
        
        # Добавляем тестовые данные для демонстрации
        self._add_test_data()
    
    def _add_test_data(self):
        """Добавить тестовые данные"""
        # Тестовые даты (завтра + несколько дней)
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
        
        print(f"[LOCAL] 📊 Добавлено {len(test_data)} тестовых записей с датами")
    
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
        """Получить доступные даты (до 6 рабочих дней)"""
        # Логика для локального режима
        today = datetime.now()
        available_dates = []
        
        # Ищем рабочие дни (есть хотя бы одна группа с квотой > 0)
        for i in range(1, 6):  # Проверяем 30 дней вперед
            if len(available_dates) >= 6:
                break
                
            check_date = today + timedelta(days=i)
            day_of_week = self._get_day_of_week_ru(check_date)
            
            # Проверяем, есть ли квоты на этот день
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
        return days[date_obj.weekday()]  # weekday() возвращает 0-6
    
    def get_free_times(self, date: str, blood_group: str) -> dict:
        """Получить свободное время для конкретной даты"""
        try:
            # Получаем день недели из даты
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_of_week = self._get_day_of_week_ru(date_obj)
            
            if day_of_week not in self.quotas:
                return {"status": "error", "data": "Неверная дата"}
            
            # Получаем квоту для группы крови
            if blood_group not in self.quotas[day_of_week]:
                return {"status": "error", "data": f"Неверная группа крови: {blood_group}"}
            
            quota_total = self.quotas[day_of_week][blood_group]
            
            # Собираем занятые времена для этой даты и группы
            busy_times = set()
            for user_data in self.bookings.values():
                if date in user_data:
                    booking = user_data[date]
                    if booking["blood_group"] == blood_group:
                        busy_times.add(booking["time"])
            
            # Свободные времена
            free_times = [t for t in self.working_hours if t not in busy_times]
            display_times = free_times[:12]  # Ограничиваем для отображения
            
            quota_used = len(busy_times)
            quota_remaining = max(0, quota_total - quota_used)
            
            return {
                "status": "success",
                "data": {
                    "times": display_times,
                    "quota": quota_remaining,
                    "quota_total": quota_total,
                    "quota_used": quota_used,
                    "blood_group": blood_group,
                    "day": day_of_week,
                    "date": date
                }
            }
            
        except ValueError as e:
            return {"status": "error", "data": f"Неверный формат даты: {date}"}
        except Exception as e:
            return {"status": "error", "data": f"Ошибка: {str(e)}"}
    
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
        """Зарегистрировать новую запись на конкретную дату"""
        # Получаем день недели из даты
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_of_week = self._get_day_of_week_ru(date_obj)
        except ValueError:
            return {"status": "error", "data": f"Неверный формат даты: {date}"}
        
        # Проверяем существующую запись
        existing = self.check_existing(date, user_id)
        if existing["data"]["exists"]:
            return {
                "status": "error",
                "data": f"У вас уже есть запись на {date}. Талон: {existing['data']['ticket']}, Время: {existing['data']['time']}"
            }
        
        # Проверяем занятость времени
        for user_data in self.bookings.values():
            if date in user_data and user_data[date]["time"] == time_slot and user_data[date]["blood_group"] == blood_group:
                return {
                    "status": "error",
                    "data": f"Время {time_slot} на {date} для группы крови {blood_group} уже занято. Выберите другое время."
                }
        
        # Проверяем квоту
        if day_of_week not in self.quotas or blood_group not in self.quotas[day_of_week]:
            return {"status": "error", "data": f"Нет квот для {day_of_week}, группа {blood_group}"}
        
        # Подсчитываем занятые места для этой даты и группы
        busy_count = 0
        for user_data in self.bookings.values():
            if date in user_data and user_data[date]["blood_group"] == blood_group:
                busy_count += 1
        
        if busy_count >= self.quotas[day_of_week][blood_group]:
            return {
                "status": "error",
                "data": f"На {date} для группы крови {blood_group} все квоты заняты. Выберите другую дату."
            }
        
        # Создаем запись
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
        
        # Обновляем статистику квот
        quota_remaining = self.quotas[day_of_week][blood_group] - (busy_count + 1)
        quota_total = self.quotas[day_of_week][blood_group]
        quota_used = busy_count + 1
        
        print(f"[LOCAL] 📝 Создана запись: {ticket} для user_id={user_id} на {date}")
        
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
        """Отменить запись на конкретную дату"""
        if user_id in self.bookings and date in self.bookings[user_id]:
            booking = self.bookings[user_id][date]
            
            if booking["ticket"] == ticket:
                # Удаляем запись
                del self.bookings[user_id][date]
                
                # Если у пользователя больше нет записей, удаляем его
                if not self.bookings[user_id]:
                    del self.bookings[user_id]
                
                print(f"[LOCAL] 🗑️ Отменена запись: {ticket} на {date}")
                
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
    
    def get_stats(self) -> dict:
        """Получить статистику"""
        total_bookings = sum(len(user_bookings) for user_bookings in self.bookings.values())
        total_users = len(self.bookings)
        
        day_stats = {}
        for day in self.quotas:
            day_stats[day] = {
                "quotas": self.quotas[day],
                "total_quotas": sum(self.quotas[day].values())
            }
        
        return {
            "total_bookings": total_bookings,
            "total_users": total_users,
            "day_stats": day_stats
        }

# Инициализируем локальное хранилище
local_storage = LocalStorage()

# ========== СЕРВИС ДЛЯ ТАЙМАУТА СЕССИЙ (ИСПРАВЛЕН) ==========
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

# ========== MIDDLEWARE ДЛЯ ПРОВЕРКИ ТАЙМАУТА (ИСПРАВЛЕН) ==========
async def timeout_middleware(handler, event, data):
    """Middleware для проверки таймаута сессии"""
    try:
        user_id = None
        chat_id = None
        
        # Получаем user_id и chat_id из события
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
            # Проверяем истекла ли сессия
            if session_timeout.is_session_expired(user_id):
                print(f"[TIMEOUT] ⏰ Сессия пользователя {user_id} истекла")
                
                # Получаем state из данных
                state = data.get('state')
                if state:
                    await state.clear()
                
                # Очищаем сессию
                session_timeout.clear_session(user_id)
                
                # Отправляем сообщение о таймауте только если это не callback с кнопкой main_menu
                bot = data.get('bot')
                
                # Проверяем, не является ли это callback'ом с кнопкой главного меню
                is_main_menu_callback = (
                    hasattr(event, 'callback_query') and 
                    event.callback_query and 
                    hasattr(event.callback_query, 'data') and
                    event.callback_query.data == "main_menu"
                )
                
                # Игнорируем сообщение о таймауте для кнопки главного меню
                if is_main_menu_callback:
                    print(f"[TIMEOUT] 🔄 Игнорируем таймаут для кнопки главного меню")
                    # Обновляем время активности и продолжаем обработку
                    session_timeout.update_activity(user_id)
                    return await handler(event, data)
                
                if bot and chat_id:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="⏳ *Ваша сессия истекла из-за неактивности.*\n\n"
                                 "Для продолжения работы используйте команду /start",
                            parse_mode="Markdown",
                            reply_markup=get_main_menu_keyboard()
                        )
                    except Exception as e:
                        print(f"[TIMEOUT] ❌ Ошибка отправки сообщения: {e}")
                
                # Отвечаем на callback если это callback запрос
                if hasattr(event, 'callback_query'):
                    try:
                        await event.callback_query.answer(
                            "Сессия истекла. Используйте /start",
                            show_alert=True
                        )
                    except Exception as e:
                        print(f"[TIMEOUT] ❌ Ошибка ответа на callback: {e}")
                
                return False  # Прерываем обработку
            
            # Обновляем время активности для всех остальных случаев
            session_timeout.update_activity(user_id)
    
    except Exception as e:
        print(f"[TIMEOUT] ❌ Ошибка в middleware: {e}")
    
    # Продолжаем обработку
    return await handler(event, data)

# ========== УНИВЕРСАЛЬНЫЙ API (ОБНОВЛЕНО) ==========
def get_available_dates(user_id: int) -> dict:
    """Универсальная функция получения доступных дат"""
    if MODE == "LOCAL":
        return local_storage.get_available_dates(user_id)
    elif MODE == "GOOGLE":
        return google_client.call_api("get_available_dates", {}, user_id)
    elif MODE == "HYBRID":
        result = google_client.call_api("get_available_dates", {}, user_id)
        
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
        return google_client.call_api("check_existing", {"date": date}, user_id)
    elif MODE == "HYBRID":
        result = google_client.call_api("check_existing", {"date": date}, user_id)
        
        if result["status"] == "error":
            return local_storage.check_existing(date, user_id)
        
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
    elif MODE == "GOOGLE" or MODE == "HYBRID":
        # Для Google Script запрашиваем список всех записей
        return google_client.call_api("get_user_bookings", {}, user_id)
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

def get_stats() -> dict:
    """Получить статистику"""
    if MODE == "LOCAL":
        return local_storage.get_stats()
    else:
        # Для Google Script собираем статистику из локального хранилища
        return local_storage.get_stats()

def clear_cache() -> dict:
    """Очистить кэш Google Script"""
    if MODE in ["GOOGLE", "HYBRID"]:
        return google_client.call_api("clear_cache", {})
    else:
        return {"status": "success", "data": "В локальном режиме кэш очищается автоматически"}

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
        
        # Удаляем старые запросы
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

# ========== СОСТОЯНИЯ БОТА (ОБНОВЛЕНО) ==========
class Form(StatesGroup):
    waiting_for_blood_group = State()
    waiting_for_date = State()  # Новое состояние вместо waiting_for_day
    waiting_for_time = State()

# ========== ИНЛАЙН-КЛАВИАТУРЫ (ОБНОВЛЕНО) ==========
def get_blood_group_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора группы крови (8 групп)"""
    builder = InlineKeyboardBuilder()
    
    # Группы крови в 2 колонки
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
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(blood_groups), 2):
        row = blood_groups[i:i+2]
        buttons = [InlineKeyboardButton(text=text, callback_data=callback) for text, callback in row]
        builder.row(*buttons)
    
    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return builder.as_markup()

def get_dates_keyboard(available_dates: List[dict]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора даты (две строки: день недели и дата)"""
    builder = InlineKeyboardBuilder()
    
    if not available_dates:
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_blood"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        )
        return builder.as_markup()
    
    # Добавляем кнопки с датами
    for date_info in available_dates:
        button_text = f"{date_info['day_of_week']}\n{date_info['display_date']}"
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"date_{date_info['date']}"  # "date_2026-04-12"
            )
        )
    
    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_blood"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return builder.as_markup()

def get_times_keyboard(times_list: List[str], current_step: int = 1, total_steps: int = 3) -> InlineKeyboardMarkup:
    """Клавиатура для выбора времени с прогресс-баром"""
    builder = InlineKeyboardBuilder()
    
    if not times_list:
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_date"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        )
        return builder.as_markup()
    
    # Создаем кнопки времени
    time_buttons = []
    for i, time_str in enumerate(times_list):
        time_buttons.append(
            InlineKeyboardButton(text=f"⏰ {time_str}", callback_data=f"time_{time_str}")
        )
    
    # Добавляем кнопки времени (по 3 в ряд)
    for i in range(0, len(time_buttons), 3):
        builder.row(*time_buttons[i:i+3])
    
    # Добавляем кнопки навигации
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_date"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    # Добавляем прогресс-бар
    progress = get_progress_bar(current_step, total_steps)
    builder.row(InlineKeyboardButton(text=progress, callback_data="progress_info"))
    
    return builder.as_markup()

def get_progress_bar(current: int, total: int, length: int = 8) -> str:
    """Создает текстовый прогресс-бар"""
    # Вычисляем процент выполнения
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
        InlineKeyboardButton(text="🔄 Сбросить данные", callback_data="admin_reset")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

# ========== ОСНОВНЫЕ КОМАНДЫ (ОБНОВЛЕНО) ==========
async def start_command(message: types.Message, state: FSMContext):
    """Команда /start - показывает главное меню"""
    user = message.from_user
    
    # Проверка ограничения частоты запросов
    if not rate_limiter.is_allowed(user.id):
        wait_time = int(rate_limiter.get_wait_time(user.id))
        await message.answer(
            f"⏳ Слишком много запросов. Пожалуйста, подождите {wait_time} секунд.",
            parse_mode=None
        )
        return
    
    await state.clear()
    
    # Очищаем данные о таймауте при старте
    session_timeout.clear_session(user.id)
    session_timeout.update_activity(user.id)
    
    greeting_name = user.first_name if user.first_name else "пользователь"
    
    # Информация о режиме
    mode_info = {
        "LOCAL": "🔧 Автономный режим",
        "GOOGLE": "🌐 Режим Google Script",
        "HYBRID": "⚡ Гибридный режим"
    }.get(MODE, "❓ Неизвестный режим")
    
    # Проверяем, является ли пользователь администратором
    is_admin = user.id in ADMIN_IDS
    admin_text = "\n👑 *Вы администратор* - доступны дополнительные функции" if is_admin else ""
    
    await message.answer(
        f"🎯 *Донорская станция v3.1*\n"
        f"{mode_info}\n\n"
        f"👋 Привет, {greeting_name}!{admin_text}\n\n"
        f"Я помогу вам записаться на донорство крови, "
        f"проверить доступное время или отменить запись.\n\n"
        f"*Новые возможности:*\n"
        f"• 📅 Выбор конкретной даты вместо дней недели\n"
        f"• 🩸 8 групп крови вместо 4\n"
        f"• ⏰ Автоматический поиск доступных дат\n"
        f"• 🗑️ Очистка кэша квот (для администраторов)\n\n"
        f"*Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def process_main_menu(callback: CallbackQuery, state: FSMContext):
    """Обработка главного меню"""
    user = callback.from_user
    
    # Обновляем время активности при взаимодействии с меню
    session_timeout.update_activity(user.id)
    
    # Проверка ограничения частоты запросов
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
            "Выберите вашу группа крови:",
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
    
    # Обновляем время активности
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
    
    # Извлекаем группу крови (убираем префикс "blood_")
    blood_group = callback.data[6:]  # "blood_A+" -> "A+"
    
    # Обновляем данные состояния
    await state.update_data(blood_group=blood_group)
    
    # Получаем доступные даты
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
    
    # Формируем текст с информацией о доступных датах
    dates_text = ""
    for i, date_info in enumerate(available_dates[:6]):  # Показываем до 6 дат
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
    
    # Обновляем время активности
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
    
    # Извлекаем дату из callback
    selected_date = callback.data[5:]  # "date_2026-04-12" -> "2026-04-12"
    
    # Получаем данные состояния
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
    
    # Сохраняем выбранную дату
    await state.update_data(selected_date=selected_date)
    
    # Преобразуем дату в читаемый формат для отображения
    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        display_date = date_obj.strftime("%d.%m.%Y")
        
        # Получаем день недели на русском
        days_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        day_of_week = days_ru[date_obj.weekday()]
        
    except ValueError:
        display_date = selected_date
        day_of_week = "неизвестно"
    
    # Проверяем доступные времена
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
            await callback.message.edit_text(
                f"❌ *На {display_date} ({day_of_week}) для группы {blood_group} все квоты заняты.*\n"
                f"📊 Осталось мест: {quota}\n\n"
                f"*Выберите другую дату:*",
                parse_mode="Markdown",
                reply_markup=get_dates_keyboard(response.get('available_dates', []))
            )
        await state.clear() if is_check else None
        await callback.answer()
        return
    
    if is_check:
        # Группируем время по часам для компактного отображения
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
        current_step = 2  # Текущий шаг (выбор даты)
        total_steps = 3   # Всего шагов (группа крови, дата, время)
        
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
    
    # Обновляем время активности
    session_timeout.update_activity(user.id)
    
    if callback.data == "cancel":
        await cancel_command(callback.message, state)
        await callback.answer()
        return
    
    if callback.data == "back_to_date":
        await callback.message.edit_text(
            "📅 *Выберите дату:*",
            parse_mode="Markdown",
            reply_markup=get_dates_keyboard([])  # TODO: Вернуть доступные даты
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
    
    # Проверяем наличие необходимых данных
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
    
    # Преобразуем дату для отображения
    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        display_date = date_obj.strftime("%d.%m.%Y")
    except ValueError:
        display_date = selected_date
    
    # Проверяем существующую запись
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
    
    # Регистрируем запись
    response = register(
        selected_date,
        blood_group,
        selected_time,
        user.id
    )
    
    if response['status'] == 'error':
        await callback.message.edit_text(
            f"❌ *Ошибка регистрации:* {response['data']}\n\n"
            f"Попробуйте выбрать другое время.",
            parse_mode="Markdown",
            reply_markup=get_times_keyboard(
                user_data.get('available_times', []),
                2, 3
            )
        )
        await callback.answer()
        return
    
    ticket_data = response['data']
    
    # Формируем талон
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

# ========== НЕОБХОДИМЫЕ ФУНКЦИИ КОМАНД ==========

async def cancel_command(message: types.Message, state: FSMContext):
    """Команда /cancel - отмена текущего диалога"""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "ℹ️ *Нет активного диалога для отмена.*\n"
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
        "📋 *Помощь по боту v3.1:*\n\n"
        "*Основные функции:*\n"
        "• 📋 Записаться на донорство\n"
        "• 🔍 Проверить доступное время\n"
        "• 📖 Посмотреть свои записи\n"
        "• 📊 Показать статистику\n"
        "• ❌ Отменить свою запись\n\n"
        "*Новые возможности:*\n"
        "📅 *Выбор конкретных дат* вместо дней недели\n"
        "🩸 *8 групп крови* (A+, A-, B+, B-, AB+, AB-, O+, O-)\n"
        "⚡ *Автоматический поиск* 6 ближайших рабочих дней\n"
        "⏰ *Таймаут сессии* 10 минут\n"
        "🗑️ *Очистка кэша квот* (для администраторов)\n\n"
        "*Правила:*\n"
        "📌 Одна запись в день на пользователя\n"
        "📅 Запись на ближайшие доступные даты\n"
        "👥 Квоты разделены по группам крови\n\n"
        "*Режимы работы:*\n"
        "🔧 *LOCAL* - автономный режим\n"
        "🌐 *GOOGLE* - данные в Google Таблицах\n"
        "⚡ *HYBRID* - автоматическое переключение\n\n"
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
        # Создаем клавиатуру с кнопками отмены
        builder = InlineKeyboardBuilder()
        
        bookings_text = ""
        for i, booking in enumerate(bookings):
            # Форматируем дату для отображения
            try:
                date_obj = datetime.strptime(booking['date'], "%Y-%m-%d")
                display_date = date_obj.strftime("%d.%m.%Y")
            except ValueError:
                display_date = booking['date']
            
            bookings_text += f"• *{display_date}* ({booking['day']}): {booking['time']} (талон: {booking['ticket']}, группа: {booking['blood_group']})\n"
            
            # Добавляем кнопку отмены для каждой записи
            builder.row(
                InlineKeyboardButton(
                    text=f"❌ Отменить запись на {display_date}",
                    callback_data=f"cancel_ask_{booking['date']}_{booking['ticket']}"
                )
            )
        
        # Добавляем кнопку возврата в главное меню
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
    stats = get_stats()
    
    total_bookings = stats["total_bookings"]
    total_users = stats["total_users"]
    
    day_stats_text = ""
    for day, data in stats["day_stats"].items():
        day_short = day[:3]
        total_quotas = data.get("total_quotas", 0)
        quotas_text = ""
        
        if "quotas" in data:
            for bg, q in data["quotas"].items():
                quotas_text += f"{bg}: {q}, "
        
        day_stats_text += f"• *{day}*: всего {total_quotas} мест ({quotas_text.rstrip(', ')})\n"
    
    mode_info = {
        "LOCAL": "🔧 *Автономный режим*\n⚠️ *Внимание:* При перезапуске бота статистика сбросится!",
        "GOOGLE": "🌐 *Режим Google Script*\n✅ Данные сохраняются в Google Таблицах",
        "HYBRID": "⚡ *Гибридный режим*\n🔄 Автоматическое переключение между режимами"
    }.get(MODE, "")
    
    stats_text = (
        f"📊 *Статистика донорской станции v3.1*\n\n"
        f"👥 *Всего пользователей:* {total_users}\n"
        f"📋 *Всего записей:* {total_bookings}\n\n"
        f"*Квоты по дням:*\n{day_stats_text}\n"
        f"{mode_info}"
    )
    
    # Добавляем кнопки администрирования для админов
    if message.from_user.id in ADMIN_IDS:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🗑️ Очистить кэш квот", callback_data="admin_clear_cache"),
            InlineKeyboardButton(text="🔄 Сбросить данные", callback_data="admin_reset")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
        )
        reply_markup = builder.as_markup()
    else:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
        )
        reply_markup = builder.as_markup()
    
    await message.answer(
        stats_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def reset_command(message: types.Message):
    """Команда /reset - сбросить все данные (только для админов)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ *У вас нет прав для выполнения этой команды.*",
            parse_mode="Markdown"
        )
        return
    
    local_storage.reset_data()
    
    await message.answer(
        "✅ *Все данные успешно сброшены!*\n\n"
        "Тестовые данные восстановлены.\n"
        "Все пользовательские записи удалены.",
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

async def process_cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены записи и админских действий"""
    try:
        # Обновляем время активности
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
            # Извлекаем информацию о записи
            parts = callback.data.split("_")
            if len(parts) >= 4:
                date = parts[2]
                ticket = "_".join(parts[3:])  # На случай, если в номере талона есть подчеркивания
                
                # Отправляем запрос на отмену
                response = cancel_booking(
                    date,
                    ticket,
                    callback.from_user.id
                )
                
                if response['status'] == 'success':
                    # Форматируем дату для отображения
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
            # Запрос на подтверждение отмены
            parts = callback.data.split("_")
            if len(parts) >= 4:
                date = parts[2]
                ticket = "_".join(parts[3:])
                
                # Форматируем дату для отображения
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
        
        if callback.data == "admin_reset":
            # Проверяем, является ли пользователь админом
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
            # Проверяем, является ли пользователь админом
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ У вас нет прав для этой операции", show_alert=True)
                return
            
            # Очищаем кэш
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
    
    # Обновляем время активности
    session_timeout.update_activity(user.id)
    
    # Информация о режиме
    mode_info = {
        "LOCAL": "🔧 Автономный режим",
        "GOOGLE": "🌐 Режим Google Script",
        "HYBRID": "⚡ Гибридный режим"
    }.get(MODE, "❓ Неизвестный режим")
    
    # Проверяем, является ли пользователь администратором
    is_admin = user.id in ADMIN_IDS
    admin_text = "\n👑 *Вы администратор* - доступны дополнительные функции" if is_admin else ""
    
    await callback.message.edit_text(
        f"🎯 *Донорская станция v3.1*\n"
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
        # Обновляем время активности при нажатии на главное меню
        session_timeout.update_activity(callback.from_user.id)
        await show_main_menu_from_callback(callback)
        await state.clear()
        await callback.answer("Главное меню")

# ========== ЗАПУСК БОТА (ОБНОВЛЕНО) ==========
async def main():
    """Основная функция запуска бота"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # === SSL-ОБХОД ДЛЯ КОРПОРАТИВНОЙ СЕТИ ===
    import ssl
    import aiohttp
    from aiogram.client.session.aiohttp import AiohttpSession
    
    print("=" * 60)
    print("🚀 ЗАПУСК ДОНОРСКОГО БОТА v3.1")
    print("=" * 60)
    
    # Тестируем соединение с Google Script
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
    elif MODE == "HYBRID":
        print("⚡ Гибридный режим: Google Script + локальное хранилище")
        print("🔄 Автоматическое переключение при ошибках")
    
    print("=" * 60)
    
    # 1. Создаем SSL-контекст, который игнорирует проверки
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # 2. Создаем коннектор aiohttp с нашим SSL-контекстом
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    # 3. Создаем сессию aiohttp с нашим коннектором
    aiohttp_session = aiohttp.ClientSession(connector=connector)
    
    # 4. Создаем сессию AiohttpSession и подменяем её внутреннюю сессию
    session = AiohttpSession()
    session._session = aiohttp_session
    
    # 5. Инициализация бота
    bot = Bot(token=TOKEN, session=session)
    
    # 6. Инициализация хранилища и диспетчера
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # 7. Регистрируем middleware для таймаута
    dp.update.middleware(timeout_middleware)
    
    # 8. Регистрация команд
    dp.message.register(start_command, Command("start"))
    dp.message.register(cancel_command, Command("cancel"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(mybookings_command, Command("mybookings"))
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(reset_command, Command("reset"))
    dp.message.register(clear_cache_command, Command("clearcache"))
    
    # 9. Регистрация callback-запросов
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
        # Запуск бота
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        # Закрываем сессии при завершении
        await aiohttp_session.close()
        print("✅ Сессии закрыты")

if __name__ == "__main__":
    asyncio.run(main())