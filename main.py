"""Тестовый скрипт для проверки логов Google Script"""
import json
import requests
import time

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxeoM0H3cCSDHExiRzlYNItipN7eXOtfbJQJJyzTeNltcDY8PU3hS4P5KDeLe39uFID/exec"

def test_logs():
    """Тест для проверки логов Google Script"""
    print("🔍 ТЕСТИРОВАНИЕ ЛОГОВ GOOGLE SCRIPT")
    print("=" * 60)
    
    # 1. Тестируем прямое получение логов через doPost
    print("\n1️⃣  Тестируем doPost с параметрами логирования...")
    
    # Создаем тестовые данные с уникальным user_id
    test_data = {
        "action": "test",
        "user_id": f"test_logs_{int(time.time())}",
        "debug": True,
        "log_level": "DEBUG"
    }
    
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=test_data, timeout=10)
        print(f"📤 Отправлен запрос: {json.dumps(test_data)}")
        print(f"📥 Получен ответ: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ответ: {json.dumps(result, ensure_ascii=False)}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    
    # 2. Тестируем получение доступных дат с логированием
    print("\n2️⃣  Тестируем get_available_dates с логированием...")
    
    test_data = {
        "action": "get_available_dates",
        "user_id": f"test_dates_{int(time.time())}",
        "debug": True,
        "force_refresh": True  # Принудительно обновить кэш
    }
    
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=test_data, timeout=15)
        print(f"📤 Отправлен запрос get_available_dates")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Статус: {result.get('status')}")
            print(f"📊 Количество дат: {result.get('data', {}).get('count', 0)}")
            
            # Выводим первые 3 даты
            dates = result.get('data', {}).get('available_dates', [])
            for i, date_info in enumerate(dates[:3], 1):
                print(f"   {i}. {date_info.get('display_date')} - {date_info.get('day_of_week')}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # 3. Проверяем, есть ли возможность получить логи через API
    print("\n3️⃣  Проверяем возможность получения логов...")
    
    test_data = {
        "action": "get_stats",
        "user_id": f"test_stats_{int(time.time())}",
        "debug": True
    }
    
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=test_data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                stats = result.get('data', {})
                print(f"📊 Статистика получена:")
                print(f"   Всего записей: {stats.get('total_bookings', 0)}")
                print(f"   Всего пользователей: {stats.get('total_users', 0)}")
                
                # Проверяем квоты на четверг
                if 'day_stats' in stats and 'четверг' in stats['day_stats']:
                    thursday = stats['day_stats']['четверг']
                    print(f"\n🔍 Квоты на четверг:")
                    for blood_type, quota_info in thursday.items():
                        used = quota_info.get('used', 0)
                        total = quota_info.get('total', 0)
                        available = total - used
                        print(f"   {blood_type}: {used}/{total} (свободно: {available})")
            else:
                print(f"❌ Ошибка: {result.get('data')}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("1. После запуска этого теста проверьте View → Logs в Google Script")
    print("2. Если логи пустые, проверьте настройки развертывания")
    print("3. Убедитесь, что проект Google Script активен")
    print("=" * 60)

if __name__ == "__main__":
    test_logs()
