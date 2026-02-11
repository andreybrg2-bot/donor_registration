"""
Проверка связи бота с Google Apps Script
Автономный скрипт для проверки get_available_dates()
Запуск: python test_google_connection.py
"""

import json
import requests
import time
from datetime import datetime

# ========== КОНФИГУРАЦИЯ ==========
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxeoM0H3cCSDHExiRzlYNItipN7eXOtfbJQJJyzTeNltcDY8PU3hS4P5KDeLe39uFID/exec"
TEST_USER_ID = 5097581039
MODE = "GOOGLE"  # Проверяем в режиме GOOGLE

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
        print("🔗 Тестирование соединения с Google Script...")
        try:
            response = self.session.post(
                self.script_url,
                json={"action": "test"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Соединение успешно: {data.get('status')}")
                if 'data' in data:
                    print(f"   Сообщение: {data['data'].get('message', 'Нет сообщения')}")
                return data
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                return {"status": "error", "data": f"HTTP ошибка: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            print("⏱️ Таймаут подключения")
            return {"status": "error", "data": "Таймаут подключения к Google Script"}
        except requests.exceptions.ConnectionError:
            print("🔌 Ошибка соединения")
            return {"status": "error", "data": "Ошибка соединения с Google Script"}
        except Exception as e:
            print(f"❌ Неизвестная ошибка: {str(e)}")
            return {"status": "error", "data": f"Неизвестная ошибка: {str(e)}"}
    
    def call_api(self, action: str, data: dict = None, user_id: int = None) -> dict:
        """Вызвать API Google Script с кэшированием"""
        if data is None:
            data = {}
            
        cache_key = f"{action}_{user_id}_{json.dumps(data, sort_keys=True)}"
        
        # Проверяем кэш
#        if action in ["get_available_dates"]:
#            if cache_key in self.cache:
#                cache_age = time.time() - self.cache_time.get(cache_key, 0)
#                if cache_age < 300:  # Кэш на 5 минут
#                    print(f"💾 Используем кэшированные данные для {action}")
 #                   return self.cache[cache_key]
        
        try:
            payload = {"action": action, **data}
            if user_id:
                payload["user_id"] = str(user_id)
            
            print(f"📤 Отправка запроса {action}: {data}")
            response = self.session.post(
                self.script_url,
                json=payload,
                timeout=self.timeout
            )
            
            print(f"📥 Получен ответ: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Успешно: {result.get('status')}")
                
                # Сохраняем в кэш
                if action in ["get_available_dates"]:
                    self.cache[cache_key] = result
                    self.cache_time[cache_key] = time.time()
                    print(f"💾 Данные сохранены в кэш. Ключ: {cache_key[:50]}...")
                
                return result
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                return {"status": "error", "data": f"HTTP ошибка: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            print("⏱️ Таймаут запроса")
            return {"status": "error", "data": "Таймаут подключения к Google Script"}
        except requests.exceptions.ConnectionError:
            print("🔌 Ошибка соединения")
            return {"status": "error", "data": "Ошибка соединения с Google Script"}
        except Exception as e:
            print(f"❌ Неизвестная ошибка: {str(e)}")
            return {"status": "error", "data": f"Неизвестная ошибка: {str(e)}"}

# ========== ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (ДЛЯ СРАВНЕНИЯ) ==========
class LocalStorage:
    """Локальное хранилище данных для сравнения"""
    
    def __init__(self):
        self.quotas = {
            "понедельник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "вторник": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "среда": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "четверг": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "пятница": {"A+": 10, "A-": 5, "B+": 10, "B-": 5, "AB+": 5, "AB-": 3, "O+": 10, "O-": 5},
            "суббота": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4},
            "воскресенье": {"A+": 8, "A-": 4, "B+": 8, "B-": 4, "AB+": 3, "AB-": 2, "O+": 8, "O-": 4}
        }
    
    def get_available_dates(self, user_id: int) -> dict:
        """Получить доступные даты (локально)"""
        today = datetime.now()
        available_dates = []
        
        for i in range(1, 30):
            if len(available_dates) >= 6:
                break
                
            check_date = today.replace(day=today.day + i)
            days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
            day_of_week = days[check_date.weekday()]
            
            # Проверяем квоты на этот день
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
                "message": f"Локально найдено {len(available_dates)} дат",
                "count": len(available_dates)
            }
        }

# ========== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ==========
def get_available_dates(user_id: int) -> dict:
    """Универсальная функция получения доступных дат"""
    if MODE == "LOCAL":
        return local_storage.get_available_dates(user_id)
    elif MODE == "GOOGLE":
        return google_client.call_api("get_available_dates", {}, user_id)
    else:
        return {"status": "error", "data": "Неизвестный режим работы"}

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    print("=" * 60)
    print("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ БОТА К GOOGLE SCRIPT")
    print("=" * 60)
    
    # Инициализация
    global google_client, local_storage
    google_client = GoogleScriptClient(GOOGLE_SCRIPT_URL)
    local_storage = LocalStorage()
    
    print(f"\n⚙️  НАСТРОЙКИ:")
    print(f"  Google Script URL: {GOOGLE_SCRIPT_URL}")
    print(f"  Режим работы: {MODE}")
    print(f"  Тестовый User ID: {TEST_USER_ID}")
    
    # 1. Тестирование соединения
    print("\n" + "=" * 60)
    print("1️⃣  ТЕСТИРОВАНИЕ СОЕДИНЕНИЯ")
    print("=" * 60)
    
    connection_result = google_client.test_connection()
    print(f"   Статус: {connection_result.get('status', 'error')}")
    
    if connection_result['status'] == 'error':
        print(f"   ❌ Не удалось подключиться к Google Script")
        print(f"   Причина: {connection_result.get('data', 'Неизвестная ошибка')}")
        return
    
    # 2. Получение доступных дат через Google Script
    print("\n" + "=" * 60)
    print("2️⃣  ПОЛУЧЕНИЕ ДОСТУПНЫХ ДАТ ИЗ GOOGLE SCRIPT")
    print("=" * 60)
    
    print(f"\n📊 Запрос к Google Script (режим {MODE}):")
    response = get_available_dates(TEST_USER_ID)
    
    print(f"\n📋 РЕЗУЛЬТАТ ОТ GOOGLE SCRIPT:")
    print(f"   Статус: {response['status']}")
    print(f"   Сообщение: {response['data'].get('message', 'Нет сообщения')}")
    print(f"   Количество дат: {response['data'].get('count', 0)}")
    
    # Подробная информация о датах
    if response['status'] == 'success' and response['data']['available_dates']:
        print(f"\n📅 ПОДРОБНАЯ ИНФОРМАЦИЯ О ДАТАХ:")
        for i, date_info in enumerate(response['data']['available_dates'][:10], 1):
            print(f"   {i:2d}. {date_info['display_date']} - {date_info['day_of_week']}")
    elif response['status'] == 'error':
        print(f"   ❌ Ошибка: {response['data']}")
    
    # 3. Проверка кэша
    print("\n" + "=" * 60)
    print("3️⃣  ПРОВЕРКА КЭША")
    print("=" * 60)
    
    print(f"\n💾 СОДЕРЖИМОЕ КЭША GOOGLE CLIENT:")
    print(f"   Количество записей в кэше: {len(google_client.cache)}")
    print(f"   Ключи в кэше: {list(google_client.cache.keys())}")
    
    if google_client.cache:
        print(f"\n📊 ДАННЫЕ В КЭШЕ:")
        for key, value in google_client.cache.items():
            if 'available_dates' in key:
                print(f"\n   Ключ: {key[:80]}...")
                print(f"   Значение: {json.dumps(value, ensure_ascii=False, indent=2)[:200]}...")
    
    # 4. Локальное хранилище для сравнения
    print("\n" + "=" * 60)
    print("4️⃣  СРАВНЕНИЕ С ЛОКАЛЬНЫМИ ДАННЫМИ")
    print("=" * 60)
    
    local_response = local_storage.get_available_dates(TEST_USER_ID)
    print(f"\n💻 ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (для сравнения):")
    print(f"   Количество дат: {local_response['data']['count']}")
    
    if local_response['data']['available_dates']:
        print(f"   Первые даты локально:")
        for i, date_info in enumerate(local_response['data']['available_dates'][:5], 1):
            print(f"   {i:2d}. {date_info['display_date']} - {date_info['day_of_week']}")
    
    # 5. Вывод итогов
    print("\n" + "=" * 60)
    print("🎯 ИТОГИ ПРОВЕРКИ")
    print("=" * 60)
    
    if response['status'] == 'success':
        print(f"✅ GOOGLE SCRIPT РАБОТАЕТ КОРРЕКТНО")
        print(f"   Получено {response['data']['count']} дат из таблицы")
        
        if response['data']['count'] > 0:
            first_date = response['data']['available_dates'][0]
            print(f"   Первая доступная дата: {first_date['display_date']} ({first_date['day_of_week']})")
        
        # Проверка кэша
        if google_client.cache:
            print(f"   Кэш работает: {len(google_client.cache)} записей")
        else:
            print(f"   ⚠️ Кэш пуст (возможно, данные не кэшируются)")
    else:
        print(f"❌ ПРОБЛЕМА С GOOGLE SCRIPT")
        print(f"   Ошибка: {response['data']}")
    
    print(f"\n📋 РЕКОМЕНДАЦИИ:")
    if response['status'] == 'error' or response['data']['count'] == 0:
        print("   1. Проверьте URL Google Script")
        print("   2. Убедитесь, что веб-приложение развернуто")
        print("   3. Проверьте ID таблицы в Google Script")
        print("   4. Проверьте наличие данных в таблице")
    else:
        print("   1. Соединение с Google Script работает")
        print("   2. Данные успешно получаются")
        print("   3. Проверьте другие функции бота")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
    
    input("\nНажмите Enter для выхода...")
    


