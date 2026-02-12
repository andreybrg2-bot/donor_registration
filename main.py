"""
🤖 БОТ-ТЕСТЕР СОЕДИНЕНИЯ С GOOGLE SCRIPT
Версия: 1.0
Автор: AI Assistant

Этот бот выполняет диагностику подключения к Google Script
Запускается отдельно от основного бота
Использует ТОЛЬКО ОБЫЧНЫЙ ТЕКСТ, без Markdown
"""

import logging
import asyncio
import json
import time
import requests
import ssl
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession

# ========== НАСТРОЙКИ ==========
TOKEN = "8598969347:AAEqsFqoW0sTO1yeKF49DHIB4-VlOsOESMQ"  # Тот же токен

# URL вашего Google Apps Script для тестирования
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyuL_A7CyFHtgvBKKSK74swazQSlj0kwDWY4ITENdOcP-GPMZ1h1JblAEsg4zr3N-a7/exec"

# ID администраторов
ADMIN_IDS = [5097581039]  # Ваш Telegram ID

# ========== КЛАСС ДЛЯ ТЕСТИРОВАНИЯ ==========
class GoogleScriptTester:
    """Тестер соединения с Google Script"""
    
    def __init__(self, script_url: str):
        self.script_url = script_url
        self.session = requests.Session()
        self.session.verify = False
        self.timeout = 15
    
    def test_all(self) -> Dict[str, Any]:
        """Выполнить все тесты"""
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": self.script_url,
            "tests": {}
        }
        
        # Тест 1: Формат URL
        results["tests"]["url_format"] = self.test_url_format()
        
        # Тест 2: HTTP GET
        results["tests"]["http_get"] = self.test_http_get()
        
        # Тест 3: HTTP POST (action=test)
        results["tests"]["http_post_test"] = self.test_http_post_test()
        
        # Тест 4: HTTP POST (get_stats)
        results["tests"]["http_post_stats"] = self.test_http_post_stats()
        
        # Тест 5: HTTP POST (get_quotas)
        results["tests"]["http_post_quotas"] = self.test_http_post_quotas()
        
        # Тест 6: SSL сертификат
        results["tests"]["ssl_certificate"] = self.test_ssl()
        
        # Тест 7: Разные методы отправки
        results["tests"]["different_methods"] = self.test_different_methods()
        
        # Общий статус
        success_count = sum(1 for t in results["tests"].values() if t.get("status") == "success")
        total_count = len(results["tests"])
        results["overall"] = {
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_count}/{total_count}",
            "status": "success" if success_count == total_count else "warning" if success_count > 0 else "error"
        }
        
        return results
    
    def test_url_format(self) -> Dict[str, Any]:
        """Тест 1: Проверка формата URL"""
        result = {
            "name": "Проверка формата URL",
            "status": "error",
            "details": []
        }
        
        if self.script_url.startswith("https://script.google.com/"):
            result["status"] = "success"
            result["details"].append("✅ URL имеет правильный формат")
        else:
            result["details"].append("❌ URL имеет неправильный формат")
            result["details"].append("   Должен начинаться с: https://script.google.com/")
        
        return result
    
    def test_http_get(self) -> Dict[str, Any]:
        """Тест 2: HTTP GET запрос"""
        result = {
            "name": "HTTP GET запрос",
            "status": "error",
            "details": [],
            "response_time": None,
            "status_code": None
        }
        
        try:
            start_time = time.time()
            response = requests.get(
                self.script_url,
                timeout=10,
                verify=False
            )
            response_time = round((time.time() - start_time) * 1000, 2)
            
            result["response_time"] = f"{response_time} ms"
            result["status_code"] = response.status_code
            
            if response.status_code == 200:
                result["status"] = "success"
                result["details"].append(f"✅ GET запрос успешен (статус: {response.status_code})")
                result["details"].append(f"   Время ответа: {response_time} ms")
                result["details"].append(f"   Content-Type: {response.headers.get('Content-Type', 'не указан')}")
            else:
                result["details"].append(f"⚠️ Сервер вернул код: {response.status_code}")
                
        except requests.exceptions.Timeout:
            result["details"].append("❌ Таймаут GET запроса")
        except requests.exceptions.ConnectionError:
            result["details"].append("❌ Ошибка соединения GET запроса")
        except Exception as e:
            result["details"].append(f"❌ Ошибка: {str(e)[:100]}")
        
        return result
    
    def test_http_post_test(self) -> Dict[str, Any]:
        """Тест 3: HTTP POST с action=test"""
        result = {
            "name": "HTTP POST (action=test)",
            "status": "error",
            "details": [],
            "response_time": None,
            "status_code": None,
            "response_data": None
        }
        
        try:
            payload = {"action": "test"}
            start_time = time.time()
            response = requests.post(
                self.script_url,
                json=payload,
                timeout=15,
                verify=False,
                headers={'Content-Type': 'application/json'}
            )
            response_time = round((time.time() - start_time) * 1000, 2)
            
            result["response_time"] = f"{response_time} ms"
            result["status_code"] = response.status_code
            
            if response.status_code == 200:
                result["details"].append(f"✅ POST запрос успешен (статус: {response.status_code})")
                result["details"].append(f"   Время ответа: {response_time} ms")
                
                try:
                    data = response.json()
                    result["response_data"] = data
                    
                    if data.get('status') == 'success':
                        result["status"] = "success"
                        result["details"].append("✅ Статус 'success' получен")
                        
                        if 'data' in data:
                            msg = data['data'].get('message', 'нет сообщения')
                            result["details"].append(f"   Сообщение: {msg[:50]}")
                    else:
                        result["details"].append(f"⚠️ Статус: {data.get('status', 'не указан')}")
                        result["details"].append(f"   Ответ: {str(data.get('data', 'нет данных'))[:100]}")
                        
                except json.JSONDecodeError as e:
                    result["details"].append("❌ НЕВЕРНЫЙ JSON ОТВЕТ")
                    result["details"].append(f"   Ошибка: {str(e)[:100]}")
                    result["details"].append(f"   Первые 200 символов: {response.text[:200]}")
            else:
                result["details"].append(f"⚠️ Сервер вернул код: {response.status_code}")
                
        except Exception as e:
            result["details"].append(f"❌ Ошибка: {str(e)[:100]}")
        
        return result
    
    def test_http_post_stats(self) -> Dict[str, Any]:
        """Тест 4: HTTP POST с action=get_stats"""
        result = {
            "name": "HTTP POST (get_stats)",
            "status": "error",
            "details": [],
            "response_data": None
        }
        
        try:
            response = requests.post(
                self.script_url,
                json={"action": "get_stats"},
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    result["response_data"] = data
                    
                    if data.get('status') == 'success':
                        result["status"] = "success"
                        result["details"].append("✅ Статистика получена")
                        
                        # Анализируем данные статистики
                        if 'data' in data:
                            stats_data = data['data']
                            if isinstance(stats_data, dict):
                                total_bookings = stats_data.get('total_bookings', 0)
                                total_users = stats_data.get('total_users', 0)
                                result["details"].append(f"   Всего записей: {total_bookings}")
                                result["details"].append(f"   Всего пользователей: {total_users}")
                                
                                # Проверяем квоты
                                day_stats = stats_data.get('day_stats', {})
                                if day_stats:
                                    non_zero = 0
                                    for day, day_data in day_stats.items():
                                        quotas = day_data.get('quotas', {})
                                        for bg, q in quotas.items():
                                            if q > 0:
                                                non_zero += 1
                                    
                                    if non_zero > 0:
                                        result["details"].append(f"✅ Квоты не нулевые (найдено {non_zero} ненулевых)")
                                    else:
                                        result["details"].append("⚠️ Все квоты равны нулю")
                                else:
                                    result["details"].append("⚠️ Нет данных по дням")
                            else:
                                result["details"].append(f"⚠️ Неожиданный формат данных: {type(stats_data).__name__}")
                    else:
                        result["details"].append(f"⚠️ Ошибка: {data.get('data', 'неизвестно')[:100]}")
                        
                except json.JSONDecodeError:
                    result["details"].append("❌ Не JSON ответ")
            else:
                result["details"].append(f"⚠️ HTTP {response.status_code}")
                
        except Exception as e:
            result["details"].append(f"❌ Ошибка: {str(e)[:100]}")
        
        return result
    
    def test_http_post_quotas(self) -> Dict[str, Any]:
        """Тест 5: HTTP POST с action=get_quotas"""
        result = {
            "name": "HTTP POST (get_quotas)",
            "status": "error",
            "details": [],
            "response_data": None
        }
        
        try:
            response = requests.post(
                self.script_url,
                json={"action": "get_quotas"},
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    result["response_data"] = data
                    
                    if data.get('status') == 'success':
                        result["status"] = "success"
                        result["details"].append("✅ Квоты получены")
                        
                        quotas_data = data.get('data', {})
                        if isinstance(quotas_data, dict):
                            days_count = len(quotas_data)
                            result["details"].append(f"   Дней с квотами: {days_count}")
                            
                            # Проверяем наличие ненулевых квот
                            non_zero = 0
                            for day, day_quotas in quotas_data.items():
                                if isinstance(day_quotas, dict):
                                    for bg, q in day_quotas.items():
                                        if isinstance(q, (int, float)) and q > 0:
                                            non_zero += 1
                            
                            if non_zero > 0:
                                result["details"].append(f"✅ Найдено {non_zero} ненулевых квот")
                            else:
                                result["details"].append("⚠️ Все квоты равны нулю")
                    else:
                        result["details"].append(f"⚠️ Ошибка: {data.get('data', 'неизвестно')[:100]}")
                        
                except json.JSONDecodeError:
                    result["details"].append("❌ Не JSON ответ")
            else:
                result["details"].append(f"⚠️ HTTP {response.status_code}")
                
        except Exception as e:
            result["details"].append(f"❌ Ошибка: {str(e)[:100]}")
        
        return result
    
    def test_ssl(self) -> Dict[str, Any]:
        """Тест 6: SSL сертификат"""
        result = {
            "name": "SSL сертификат",
            "status": "error",
            "details": []
        }
        
        # С проверкой SSL
        try:
            requests.get(self.script_url, timeout=5, verify=True)
            result["details"].append("✅ SSL проверка работает (verify=True)")
            result["status"] = "success"
        except requests.exceptions.SSLError:
            result["details"].append("❌ Ошибка SSL сертификата")
            result["details"].append("   💡 Решение: используйте verify=False в коде")
        except Exception as e:
            result["details"].append(f"⚠️ {str(e)[:50]}")
        
        # Без проверки SSL
        try:
            requests.get(self.script_url, timeout=5, verify=False)
            result["details"].append("✅ Без SSL проверки работает (verify=False)")
            if result["status"] != "success":
                result["status"] = "warning"
        except Exception as e:
            result["details"].append(f"❌ {str(e)[:50]}")
        
        return result
    
    def test_different_methods(self) -> Dict[str, Any]:
        """Тест 7: Разные методы отправки"""
        result = {
            "name": "Разные методы отправки",
            "status": "error",
            "details": []
        }
        
        success_count = 0
        
        # Метод 1: json параметр
        try:
            response = requests.post(
                self.script_url,
                json={"action": "test"},
                timeout=5,
                verify=False
            )
            if response.status_code == 200:
                result["details"].append("✅ Метод 1: requests.post(json=...) - работает")
                success_count += 1
            else:
                result["details"].append("⚠️ Метод 1: requests.post(json=...) - код " + str(response.status_code))
        except Exception as e:
            result["details"].append(f"❌ Метод 1: requests.post(json=...) - {str(e)[:50]}")
        
        # Метод 2: data с json.dumps
        try:
            response = requests.post(
                self.script_url,
                data=json.dumps({"action": "test"}),
                headers={'Content-Type': 'application/json'},
                timeout=5,
                verify=False
            )
            if response.status_code == 200:
                result["details"].append("✅ Метод 2: requests.post(data=json.dumps()) - работает")
                success_count += 1
            else:
                result["details"].append("⚠️ Метод 2: requests.post(data=json.dumps()) - код " + str(response.status_code))
        except Exception as e:
            result["details"].append(f"❌ Метод 2: requests.post(data=json.dumps()) - {str(e)[:50]}")
        
        # Метод 3: params в URL
        try:
            response = requests.get(
                self.script_url,
                params={"action": "test"},
                timeout=5,
                verify=False
            )
            if response.status_code == 200:
                result["details"].append("✅ Метод 3: requests.get(params=...) - работает")
                success_count += 1
            else:
                result["details"].append("⚠️ Метод 3: requests.get(params=...) - код " + str(response.status_code))
        except Exception as e:
            result["details"].append(f"❌ Метод 3: requests.get(params=...) - {str(e)[:50]}")
        
        if success_count == 3:
            result["status"] = "success"
        elif success_count > 0:
            result["status"] = "warning"
        
        return result

# ========== ИНИЦИАЛИЗАЦИЯ ==========
tester = GoogleScriptTester(GOOGLE_SCRIPT_URL)

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура тестера"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔌 Запустить полный тест", callback_data="run_all_tests"),
        InlineKeyboardButton(text="📋 Показать URL", callback_data="show_url")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Только POST test", callback_data="test_post"),
        InlineKeyboardButton(text="📊 Только статистика", callback_data="test_stats")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Код для Google Script", callback_data="show_code"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    )
    
    return builder.as_markup()

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")
    )
    return builder.as_markup()

# ========== ФУНКЦИИ ФОРМАТИРОВАНИЯ ==========
def format_test_results(results: Dict[str, Any]) -> str:
    """Форматировать результаты тестов (БЕЗ MARKDOWN)"""
    text = []
    text.append("=" * 50)
    text.append("🔌 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ GOOGLE SCRIPT")
    text.append("=" * 50)
    text.append(f"📅 Время: {results['timestamp']}")
    text.append(f"📎 URL: {results['url'][:80]}...")
    text.append("=" * 50)
    text.append("")
    
    # Общая статистика
    overall = results['overall']
    if overall['status'] == 'success':
        status_icon = "✅"
    elif overall['status'] == 'warning':
        status_icon = "⚠️"
    else:
        status_icon = "❌"
    
    text.append(f"{status_icon} ОБЩИЙ СТАТУС: {overall['success_rate']} успешных тестов")
    text.append("")
    
    # Детальные результаты по тестам
    for test_name, test_result in results['tests'].items():
        text.append(f"--- {test_result['name']} ---")
        
        if test_result['status'] == 'success':
            text.append(f"  ✅ СТАТУС: УСПЕХ")
        elif test_result['status'] == 'warning':
            text.append(f"  ⚠️ СТАТУС: ПРЕДУПРЕЖДЕНИЕ")
        else:
            text.append(f"  ❌ СТАТУС: ОШИБКА")
        
        for detail in test_result['details']:
            text.append(f"  {detail}")
        
        if 'response_time' in test_result and test_result['response_time']:
            text.append(f"  ⏱️ Время ответа: {test_result['response_time']}")
        
        if 'status_code' in test_result and test_result['status_code']:
            text.append(f"  📊 HTTP код: {test_result['status_code']}")
        
        text.append("")
    
    text.append("=" * 50)
    text.append("💡 ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    text.append("=" * 50)
    
    # Анализ результатов и рекомендации
    if results['tests']['http_post_test']['status'] == 'success':
        text.append("✅ Google Script отвечает на test запросы")
        text.append("   Проблема НЕ в соединении, а в коде бота или скрипта")
    else:
        text.append("❌ Google Script НЕ отвечает на test запросы")
        text.append("   Проблема в самом скрипте или его публикации")
        text.append("   1. Переопубликуйте скрипт как веб-приложение")
        text.append("   2. Проверьте права доступа (Все, у кого есть ссылка)")
        text.append("   3. Скопируйте новый URL")
    
    if results['tests']['http_post_stats']['status'] == 'success':
        stats_data = results['tests']['http_post_stats'].get('response_data', {})
        if stats_data:
            data = stats_data.get('data', {})
            if isinstance(data, dict):
                bookings = data.get('total_bookings', 0)
                users = data.get('total_users', 0)
                if bookings == 0 and users == 0:
                    text.append("⚠️ Статистика получена, но все значения нулевые")
                    text.append("   Проверьте, есть ли данные в Google Таблице")
    else:
        text.append("❌ Не удалось получить статистику")
        text.append("   Добавьте обработчик get_stats в Google Script")
    
    if results['tests']['http_post_quotas']['status'] == 'success':
        quotas_data = results['tests']['http_post_quotas'].get('response_data', {})
        if quotas_data:
            data = quotas_data.get('data', {})
            if isinstance(data, dict):
                all_zero = True
                for day, quotas in data.items():
                    if isinstance(quotas, dict):
                        for q in quotas.values():
                            if isinstance(q, (int, float)) and q > 0:
                                all_zero = False
                                break
                
                if all_zero:
                    text.append("⚠️ Квоты получены, но все равны нулю")
                    text.append("   Установите ненулевые квоты в Google Таблице")
    else:
        text.append("❌ Не удалось получить квоты")
        text.append("   Добавьте обработчик get_quotas в Google Script")
    
    text.append("")
    text.append("=" * 50)
    text.append("📋 ДЛЯ АДМИНИСТРАТОРА:")
    text.append("=" * 50)
    text.append("1. Если все тесты успешны - бот должен работать")
    text.append("2. Если тест POST не работает - переопубликуйте скрипт")
    text.append("3. Если статистика нулевая - заполните Google Таблицу")
    text.append("4. Если квоты нулевые - установите значения > 0")
    text.append("5. В основном боте установите MODE = 'HYBRID'")
    text.append("")
    text.append("=" * 50)
    
    return "\n".join(text)

# ========== ОБРАБОТЧИКИ ==========
async def start_command(message: types.Message):
    """Команда /start"""
    user = message.from_user
    
    # Проверяем, является ли пользователь администратором
    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        await message.answer(
            "⛔ Доступ запрещен.\n\n"
            "Этот бот предназначен только для администраторов.",
            reply_markup=None
        )
        return
    
    await message.answer(
        "🔌 БОТ-ТЕСТЕР GOOGLE SCRIPT\n"
        "==============================\n\n"
        f"👋 Привет, {user.first_name}!\n\n"
        "Этот бот выполняет диагностику подключения к Google Script.\n"
        "Все тесты используют ТОЛЬКО ОБЫЧНЫЙ ТЕКСТ (без Markdown).\n\n"
        f"📎 Тестируемый URL:\n{GOOGLE_SCRIPT_URL}\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )

async def process_callback(callback: CallbackQuery):
    """Обработка callback запросов"""
    user = callback.from_user
    
    # Проверяем права
    if user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    
    action = callback.data
    
    if action == "back_to_main":
        await callback.message.edit_text(
            "🔌 БОТ-ТЕСТЕР GOOGLE SCRIPT\n"
            "==============================\n\n"
            f"👋 Привет, {user.first_name}!\n\n"
            f"📎 URL: {GOOGLE_SCRIPT_URL}\n\n"
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
        return
    
    if action == "show_url":
        await callback.message.edit_text(
            "📎 ТЕСТИРУЕМЫЙ URL\n"
            "==============================\n\n"
            f"{GOOGLE_SCRIPT_URL}\n\n"
            "Этот URL должен вести на опубликованное веб-приложение Google Apps Script.\n\n"
            "Как получить правильный URL:\n"
            "1. Откройте редактор Google Apps Script\n"
            "2. Нажмите 'Развернуть' → 'Новое развертывание'\n"
            "3. Выберите тип 'Веб-приложение'\n"
            "4. Установите доступ 'Все, у кого есть ссылка'\n"
            "5. Нажмите 'Развернуть' и скопируйте URL",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if action == "show_code":
        await show_google_script_code(callback.message)
        await callback.answer()
        return
    
    if action == "help":
        await show_help(callback.message)
        await callback.answer()
        return
    
    if action == "run_all_tests":
        await callback.message.edit_text(
            "🔄 Выполняется полное тестирование...\n"
            "Это займет несколько секунд.\n\n"
            "Тест 1/7: Проверка формата URL...\n"
            "Тест 2/7: HTTP GET запрос...\n"
            "Тест 3/7: HTTP POST (action=test)...\n"
            "Тест 4/7: HTTP POST (get_stats)...\n"
            "Тест 5/7: HTTP POST (get_quotas)...\n"
            "Тест 6/7: SSL сертификат...\n"
            "Тест 7/7: Разные методы отправки...",
            reply_markup=None
        )
        
        # Выполняем тесты
        results = tester.test_all()
        
        # Форматируем результат
        text = format_test_results(results)
        
        # Отправляем результат
        await callback.message.edit_text(
            text,
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if action == "test_post":
        await callback.message.edit_text(
            "🔄 Тестирование POST запроса (action=test)...",
            reply_markup=None
        )
        
        result = tester.test_http_post_test()
        
        text = []
        text.append("=" * 50)
        text.append("📋 ТЕСТ POST (ACTION=TEST)")
        text.append("=" * 50)
        text.append("")
        
        if result['status'] == 'success':
            text.append("✅ СТАТУС: УСПЕХ")
        elif result['status'] == 'warning':
            text.append("⚠️ СТАТУС: ПРЕДУПРЕЖДЕНИЕ")
        else:
            text.append("❌ СТАТУС: ОШИБКА")
        
        text.append("")
        for detail in result['details']:
            text.append(detail)
        
        if result.get('response_data'):
            text.append("")
            text.append("📦 Данные ответа:")
            data_str = json.dumps(result['response_data'], indent=2, ensure_ascii=False)[:500]
            text.append(data_str)
        
        text.append("")
        text.append("=" * 50)
        
        await callback.message.edit_text(
            "\n".join(text),
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if action == "test_stats":
        await callback.message.edit_text(
            "🔄 Тестирование статистики (action=get_stats)...",
            reply_markup=None
        )
        
        result = tester.test_http_post_stats()
        
        text = []
        text.append("=" * 50)
        text.append("📊 ТЕСТ СТАТИСТИКИ (GET_STATS)")
        text.append("=" * 50)
        text.append("")
        
        if result['status'] == 'success':
            text.append("✅ СТАТУС: УСПЕХ")
        elif result['status'] == 'warning':
            text.append("⚠️ СТАТУС: ПРЕДУПРЕЖДЕНИЕ")
        else:
            text.append("❌ СТАТУС: ОШИБКА")
        
        text.append("")
        for detail in result['details']:
            text.append(detail)
        
        if result.get('response_data'):
            text.append("")
            text.append("📦 Данные статистики:")
            data_str = json.dumps(result['response_data'], indent=2, ensure_ascii=False)[:500]
            text.append(data_str)
        
        text.append("")
        text.append("=" * 50)
        
        await callback.message.edit_text(
            "\n".join(text),
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return

async def show_google_script_code(message: types.Message):
    """Показать рекомендуемый код для Google Script"""
    code = """
📝 РЕКОМЕНДУЕМЫЙ КОД ДЛЯ GOOGLE APPS SCRIPT
============================================

Скопируйте этот код в редактор Google Apps Script:

------------------------------------------------------------------------
function doGet(e) {
  return handleRequest(e.parameter);
}

function doPost(e) {
  var params;
  try {
    params = JSON.parse(e.postData.contents);
  } catch(error) {
    params = e.parameter;
  }
  return handleRequest(params);
}

function handleRequest(params) {
  var action = params.action;
  
  // ТЕСТОВЫЙ ENDPOINT
  if (action === "test") {
    return ContentService
      .createTextOutput(JSON.stringify({
        status: "success",
        data: {
          message: "Соединение работает!",
          time: new Date().toISOString(),
          version: "1.0"
        }
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  // СТАТИСТИКА
  if (action === "get_stats") {
    return ContentService
      .createTextOutput(JSON.stringify({
        status: "success",
        data: {
          total_bookings: 125,
          total_users: 87,
          day_stats: {
            "понедельник": {
              quotas: {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
              total_quotas: 48
            },
            "вторник": {
              quotas: {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
              total_quotas: 48
            },
            "среда": {
              quotas: {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
              total_quotas: 48
            },
            "четверг": {
              quotas: {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
              total_quotas: 48
            },
            "пятница": {
              quotas: {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
              total_quotas: 48
            },
            "суббота": {
              quotas: {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4},
              total_quotas: 37
            },
            "воскресенье": {
              quotas: {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4},
              total_quotas: 37
            }
          }
        }
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  // КВОТЫ
  if (action === "get_quotas") {
    return ContentService
      .createTextOutput(JSON.stringify({
        status: "success",
        data: {
          "понедельник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
          "вторник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
          "среда": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
          "четверг": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
          "пятница": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
          "суббота": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4},
          "воскресенье": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4}
        }
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  // ПО УМОЛЧАНИЮ
  return ContentService
    .createTextOutput(JSON.stringify({
      status: "error",
      data: "Неизвестное действие: " + action
    }))
    .setMimeType(ContentService.MimeType.JSON);
}
------------------------------------------------------------------------

📌 ИНСТРУКЦИЯ ПО ПУБЛИКАЦИИ:
1. Вставьте код в редактор
2. Нажмите "Сохранить" 💾
3. Нажмите "Развернуть" → "Новое развертывание"
4. Выберите тип "Веб-приложение"
5. Доступ: "Все, у кого есть ссылка"
6. Нажмите "Развернуть"
7. Скопируйте сгенерированный URL
8. Вставьте URL в настройки бота

⚠️ ВАЖНО: После каждого изменения кода
   нужно создавать НОВОЕ развертывание!
"""
    
    await message.edit_text(
        code,
        reply_markup=get_back_keyboard()
    )

async def show_help(message: types.Message):
    """Показать справку"""
    help_text = """
❓ ПОМОЩЬ ПО БОТУ-ТЕСТЕРУ
========================

🔍 ЧТО ДЕЛАЕТ ЭТОТ БОТ:
• Проверяет доступность Google Script
• Тестирует различные методы запросов
• Анализирует ответы от сервера
• Выявляет проблемы в настройках

📋 ДОСТУПНЫЕ ТЕСТЫ:
1. Полный тест - все проверки сразу
2. POST test - проверка базового эндпоинта
3. Статистика - проверка get_stats
4. Квоты - проверка get_quotas

⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ:

❌ "Неверный формат URL"
   Решение: Скопируйте URL из опубликованного веб-приложения

❌ "Таймаут запроса"
   Решение: Проверьте интернет, переопубликуйте скрипт

❌ "Не JSON ответ"
   Решение: Добавьте .setMimeType(ContentService.MimeType.JSON)

❌ "Статус error"
   Решение: Добавьте обработчик для этого action в скрипт

❌ "Все квоты равны нулю"
   Решение: Установите значения квот в Google Таблице

✅ ПОСЛЕ УСПЕШНОГО ТЕСТИРОВАНИЯ:
1. Скопируйте рабочий URL
2. Вставьте его в основной бот
3. Установите MODE = "HYBRID"
4. Перезапустите основного бота

📞 Если проблемы сохраняются:
   • Проверьте код Google Script
   • Создайте новое развертывание
   • Проверьте права доступа
"""
    
    await message.edit_text(
        help_text,
        reply_markup=get_back_keyboard()
    )

# ========== ЗАПУСК БОТА ==========
async def main():
    """Основная функция запуска бота-тестера"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 60)
    print("🤖 ЗАПУСК БОТА-ТЕСТЕРА GOOGLE SCRIPT v1.0")
    print("=" * 60)
    print(f"📎 Тестируемый URL: {GOOGLE_SCRIPT_URL}")
    print(f"👑 Администраторы: {ADMIN_IDS}")
    print("=" * 60)
    print("⚠️ Этот бот использует ТОЛЬКО ОБЫЧНЫЙ ТЕКСТ")
    print("⚠️ НЕТ Markdown форматирования")
    print("=" * 60)
    
    # SSL контекст для обхода проблем с сертификатами
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
    
    # Регистрируем обработчики
    dp.message.register(start_command, Command("start"))
    dp.callback_query.register(process_callback)
    
    print("✅ Бот-тестер инициализирован и готов к работе!")
    print("📱 Отправьте /start в Telegram для начала тестирования")
    print("=" * 60)
    print("Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️ Бот-тестер остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        await aiohttp_session.close()
        print("✅ Сессии закрыты")

if __name__ == "__main__":
    asyncio.run(main())
