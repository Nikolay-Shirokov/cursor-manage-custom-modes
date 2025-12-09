import sqlite3
import json
import sys
import os
from typing import Dict, List, Optional
from pathlib import Path

class CustomModesManager:
    """Менеджер для управления кастомными режимами Cursor"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Автоматически определяем путь к state.vscdb
            self.db_path = self._find_state_vscdb()
        else:
            self.db_path = db_path
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"База данных не найдена: {self.db_path}")
        
        self.modes_key = "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl.persistentStorage.applicationUser"
    
    @staticmethod
    def _find_state_vscdb() -> str:
        """Автоматически находит state.vscdb в стандартных местах"""
        # Возможные пути для Windows
        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata:
                cursor_path = os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")
                if os.path.exists(cursor_path):
                    return cursor_path
        
        # Возможные пути для macOS
        elif sys.platform == "darwin":
            home = os.path.expanduser("~")
            cursor_path = os.path.join(home, "Library", "Application Support", "Cursor", "User", "globalStorage", "state.vscdb")
            if os.path.exists(cursor_path):
                return cursor_path
        
        # Возможные пути для Linux
        elif sys.platform.startswith("linux"):
            home = os.path.expanduser("~")
            cursor_path = os.path.join(home, ".config", "Cursor", "User", "globalStorage", "state.vscdb")
            if os.path.exists(cursor_path):
                return cursor_path
        
        # Если не найдено, ищем в текущей директории
        if os.path.exists("state.vscdb"):
            return "state.vscdb"
        
        # Если не найдено нигде, выбрасываем исключение
        raise FileNotFoundError(
            "Не удалось найти state.vscdb. Укажите путь явно:\n"
            "manager = CustomModesManager('/путь/к/state.vscdb')"
        )
    
    def _get_connection(self):
        """Создает подключение к базе данных"""
        return sqlite3.connect(self.db_path)
    
    def _get_composer_state(self) -> Optional[Dict]:
        """Получает composerState из базы данных"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                (self.modes_key,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                data = json.loads(result[0])
                return data.get("composerState", {})
            return None
        except Exception as e:
            print(f"Ошибка получения данных: {e}", file=sys.stderr)
            return None
    
    def _save_composer_state(self, composer_state: Dict) -> bool:
        """Сохраняет composerState в базу данных"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Получаем текущие данные
            cursor.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                (self.modes_key,)
            )
            result = cursor.fetchone()
            
            if result:
                data = json.loads(result[0])
                data["composerState"] = composer_state
                
                # Обновляем данные
                cursor.execute(
                    "UPDATE ItemTable SET value = ? WHERE key = ?",
                    (json.dumps(data, ensure_ascii=False), self.modes_key)
                )
                conn.commit()
                conn.close()
                return True
            else:
                print("Ключ не найден в базе данных", file=sys.stderr)
                conn.close()
                return False
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}", file=sys.stderr)
            return False
    
    def list_modes(self, show_builtin: bool = True) -> List[Dict]:
        """Выводит список всех режимов"""
        composer_state = self._get_composer_state()
        if not composer_state:
            return []
        
        modes = composer_state.get("modes4", [])
        
        print("=== Список режимов ===\n")
        
        builtin_ids = ["agent", "plan", "background", "chat", "spec", "debug"]
        
        result = []
        for idx, mode in enumerate(modes, 1):
            mode_id = mode.get("id", "")
            is_builtin = mode_id in builtin_ids
            
            if not show_builtin and is_builtin:
                continue
            
            mode_type = "встроенный" if is_builtin else "кастомный"
            
            print(f"{idx}. [{mode_type}] {mode.get('name', 'Без названия')}")
            print(f"   ID: {mode_id}")
            print(f"   Иконка: {mode.get('icon', 'не указана')}")
            print(f"   Описание: {mode.get('description', 'отсутствует')}")
            print(f"   AutoRun: {mode.get('autoRun', False)}")
            print(f"   AutoFix: {mode.get('autoFix', False)}")
            
            enabled_tools = mode.get('enabledTools', [])
            print(f"   Инструменты: {len(enabled_tools)} включено")
            
            enabled_mcp = mode.get('enabledMcpServers', [])
            print(f"   MCP серверы: {len(enabled_mcp)} включено")
            
            if mode.get('customRulesForAI'):
                print(f"   Кастомные правила: Да ({len(mode['customRulesForAI'])} символов)")
            
            print()
            
            result.append(mode)
        
        print(f"Всего режимов: {len(result)}")
        return result
    
    def get_mode(self, mode_id: str) -> Optional[Dict]:
        """Получает конкретный режим по ID"""
        composer_state = self._get_composer_state()
        if not composer_state:
            return None
        
        modes = composer_state.get("modes4", [])
        for mode in modes:
            if mode.get("id") == mode_id:
                return mode
        return None
    
    def export_mode(self, mode_id: str, output_file: str) -> bool:
        """Экспортирует режим в JSON файл"""
        mode = self.get_mode(mode_id)
        if not mode:
            print(f"Режим с ID '{mode_id}' не найден", file=sys.stderr)
            return False
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(mode, f, indent=2, ensure_ascii=False)
            print(f"Режим '{mode.get('name')}' экспортирован в {output_file}")
            return True
        except Exception as e:
            print(f"Ошибка экспорта: {e}", file=sys.stderr)
            return False
    
    def import_mode(self, input_file: str, mode_id: Optional[str] = None) -> bool:
        """Импортирует режим из JSON файла"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                mode = json.load(f)
            
            # Генерируем новый ID если не указан
            if mode_id:
                mode["id"] = mode_id
            elif "id" not in mode or not mode["id"]:
                import uuid
                mode["id"] = str(uuid.uuid4())
            
            # Проверяем обязательные поля
            required_fields = ["name", "icon", "thinkingLevel", "autoRun", 
                             "shouldAutoApplyIfNoEditTool", "enabledTools", 
                             "autoFix", "enabledMcpServers"]
            
            for field in required_fields:
                if field not in mode:
                    print(f"Отсутствует обязательное поле: {field}", file=sys.stderr)
                    return False
            
            # Добавляем режим
            composer_state = self._get_composer_state()
            if not composer_state:
                return False
            
            modes = composer_state.get("modes4", [])
            
            # Проверяем, не существует ли режим с таким ID
            existing_mode = None
            for idx, m in enumerate(modes):
                if m.get("id") == mode["id"]:
                    existing_mode = idx
                    break
            
            if existing_mode is not None:
                print(f"Режим с ID '{mode['id']}' уже существует. Заменяем...")
                modes[existing_mode] = mode
            else:
                modes.append(mode)
            
            composer_state["modes4"] = modes
            
            if self._save_composer_state(composer_state):
                print(f"Режим '{mode.get('name')}' успешно импортирован!")
                return True
            return False
            
        except Exception as e:
            print(f"Ошибка импорта: {e}", file=sys.stderr)
            return False
    
    def delete_mode(self, mode_id: str) -> bool:
        """Удаляет режим по ID"""
        # Проверяем, что это не встроенный режим
        builtin_ids = ["agent", "plan", "background", "chat", "spec", "debug"]
        if mode_id in builtin_ids:
            print(f"Нельзя удалить встроенный режим '{mode_id}'", file=sys.stderr)
            return False
        
        composer_state = self._get_composer_state()
        if not composer_state:
            return False
        
        modes = composer_state.get("modes4", [])
        
        # Ищем и удаляем режим
        new_modes = [m for m in modes if m.get("id") != mode_id]
        
        if len(new_modes) == len(modes):
            print(f"Режим с ID '{mode_id}' не найден", file=sys.stderr)
            return False
        
        composer_state["modes4"] = new_modes
        
        if self._save_composer_state(composer_state):
            print(f"Режим с ID '{mode_id}' успешно удален!")
            return True
        return False
    
    def create_mode_template(self, output_file: str = "mode_template.json"):
        """Создает шаблон для нового режима"""
        template = {
            "id": "YOUR_UNIQUE_ID",
            "name": "Название режима",
            "icon": "infinity",
            "description": "Описание режима (опционально)",
            "thinkingLevel": "none",
            "autoRun": False,
            "shouldAutoApplyIfNoEditTool": True,
            "enabledTools": [1, 18, 3, 6, 8, 5, 16, 7, 11, 15],
            "autoFix": True,
            "enabledMcpServers": [],
            "customRulesForAI": "# Ваши правила для AI\n\nВведите здесь инструкции для AI..."
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            print(f"Шаблон режима создан: {output_file}")
            print("\nДоступные иконки: infinity, todos, cloudUpload, chat, checklist, bug, hammer, running, fileTwo, и др.")
            print("Инструменты (enabledTools): 1-18, 41 и др.")
            print("ThinkingLevel: none, low, medium, high")
            return True
        except Exception as e:
            print(f"Ошибка создания шаблона: {e}", file=sys.stderr)
            return False


def main():
    """Главная функция с интерактивным меню"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Управление кастомными режимами Cursor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python manage_custom_modes.py
  python manage_custom_modes.py --db /путь/к/state.vscdb
  python manage_custom_modes.py --db state.vscdb
        """
    )
    
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Путь к файлу state.vscdb (если не указан, будет найден автоматически)"
    )
    
    args = parser.parse_args()
    
    try:
        manager = CustomModesManager(args.db)
        print(f"Используется база данных: {manager.db_path}")
    except FileNotFoundError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    
    while True:
        print("\n" + "="*50)
        print("Управление кастомными режимами Cursor")
        print("="*50)
        print("1. Показать все режимы")
        print("2. Показать только кастомные режимы")
        print("3. Экспортировать режим")
        print("4. Импортировать режим")
        print("5. Удалить кастомный режим")
        print("6. Создать шаблон режима")
        print("0. Выход")
        print()
        
        choice = input("Выберите действие: ").strip()
        
        if choice == "1":
            manager.list_modes(show_builtin=True)
        
        elif choice == "2":
            manager.list_modes(show_builtin=False)
        
        elif choice == "3":
            mode_id = input("Введите ID режима для экспорта: ").strip()
            output_file = input("Имя выходного файла [mode.json]: ").strip() or "mode.json"
            manager.export_mode(mode_id, output_file)
        
        elif choice == "4":
            input_file = input("Путь к JSON файлу режима: ").strip()
            mode_id = input("Новый ID (оставьте пустым для автогенерации): ").strip() or None
            manager.import_mode(input_file, mode_id)
        
        elif choice == "5":
            mode_id = input("Введите ID режима для удаления: ").strip()
            confirm = input(f"Вы уверены, что хотите удалить режим '{mode_id}'? (yes/no): ").strip().lower()
            if confirm == "yes":
                manager.delete_mode(mode_id)
        
        elif choice == "6":
            output_file = input("Имя файла шаблона [mode_template.json]: ").strip() or "mode_template.json"
            manager.create_mode_template(output_file)
        
        elif choice == "0":
            print("До свидания!")
            break
        
        else:
            print("Неверный выбор. Попробуйте снова.")
        
        input("\nНажмите Enter для продолжения...")


if __name__ == "__main__":
    main()