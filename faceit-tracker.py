import requests
import threading
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.core.window import Window
import logging
import os
import sys
from kivy.config import Config
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем API ключ из переменных окружения
API_KEY = os.getenv("FACEIT_API_KEY")
if not API_KEY:
    raise ValueError("FACEIT_API_KEY не найден в переменных окружения. Проверьте файл .env")

BASE_URL = "https://open.faceit.com/data/v4"

# Задаем цвета и размеры окна
Window.size = (800, 600)
Window.minimum_width, Window.minimum_height = 400, 300
Window.clearcolor = (0, 0, 0, 1)

# Настройка логирования только для критических ошибок
def setup_logging():
    logging.basicConfig(
        level=logging.ERROR,  # Только ERROR и CRITICAL
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('faceit_tracker')

# Использование в коде
logger = setup_logging()

# Функция проверки наличия иконки и создания её при необходимости
def ensure_icon_exists():
    """Проверяет наличие иконки и создаёт её, если не найдена"""
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faceit-icon.ico')
    
    if not os.path.exists(icon_path):
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Создаем оранжевый круг с буквой F
            size = 256
            img = Image.new('RGBA', (size, size), color=(0,0,0,0))
            
            # Рисуем
            draw = ImageDraw.Draw(img)
            margin = 10
            draw.ellipse((margin, margin, size-margin, size-margin), 
                         fill=(255, 84, 0, 255), outline=(255, 120, 50, 255), width=5)
            
            # Текст F
            try:
                font = ImageFont.truetype("arial.ttf", size//2)
            except:
                font = ImageFont.load_default()
                
            draw.text((size//2-size//6, size//2-size//3), "F", fill=(255,255,255,255), font=font)
            
            # Сохраняем как многоразмерный ICO
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(icon_path, format='ICO', sizes=sizes)
            print(f"Создана иконка по умолчанию: {icon_path}")
        except Exception as e:
            print(f"Не удалось создать иконку: {e}")
            # Создаем простой файл иконки
            with open(icon_path, 'wb') as f:
                # Минимальный валидный .ico файл
                f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x04\x00\x28\x01'
                        b'\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00'
                        b'\x00\x00\x01\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x33\x00\x00'
                        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\x00'
                        b'\x0F\xFF\xF0\x00\x0F\xFF\xF0\x00\x0F\xFF\xF0\x00\x0F\xFF\xF0\x00'
                        b'\x0F\x00\xF0\x00\x0F\x00\xF0\x00\x0F\x11\xF0\x00\x0F\x11\xF0\x00'
                        b'\x0F\xFF\xF0\x00\x0F\xFF\xF0\x00\x0F\x00\x00\x00\x0F\x00\x00\x00'
                        b'\x0F\x00\x00\x00\x0F\x00\x00\x00\x0F\xFF\xF0\x00\x00\x00\x00\x00')
    
    return icon_path

# Вызываем функцию при запуске программы
icon_path = ensure_icon_exists()

# Настраиваем название и иконку приложения до создания окна
Config.set('kivy', 'window_icon', icon_path)
Config.set('kivy', 'window_title', 'FACEIT ANALYZE')

# Основной класс для отображения статистики
class StatsLayout(BoxLayout):
    output_text = StringProperty("_")
    
    def __init__(self, **kwargs):
        super(StatsLayout, self).__init__(**kwargs)
    
    def fetch_stats(self, nickname):
        """Запускает отдельный поток для получения статистики"""
        if not nickname:
            self.update_output("[color=ff5500]Введите никнейм или ссылку на профиль[/color]")
            return
            
        self.update_output("Получение данных...")
        threading.Thread(target=self._fetch_stats_thread, args=(nickname,)).start()
    
    def _fetch_stats_thread(self, nickname):
        """Получает статистику игрока в отдельном потоке"""
        try:
            # Извлекаем никнейм из URL если пользователь ввел ссылку
            if "/" in nickname:
                parts = nickname.rstrip("/").split("/")
                nickname = parts[-1]
            
            # Получаем данные по API
            self.update_output(f"Поиск игрока {nickname}...")
            player_data = self._get_player_data(nickname)
            
            if not player_data:
                self.update_output(f"[color=ff3300]Игрок {nickname} не найден[/color]")
                return
            
            player_id = player_data.get("player_id")
            self.update_output(f"Получение статистики для {nickname} (ID: {player_id})...")
            
            # Получаем статистику для CS:2 (game_id=cs2)
            stats_data = self._get_stats_data(player_id, "cs2")
            
            # Если нет данных CS:2, попробуем получить для CS:GO
            if not stats_data or not stats_data.get("segments"):
                self.update_output(f"Статистика CS:2 для {nickname} не найдена. Пробуем CS:GO...")
                stats_data = self._get_stats_data(player_id, "csgo")
            
            # Форматируем и отображаем полученные данные
            if stats_data:
                self._format_and_display_stats(player_data, stats_data)
            else:
                self.update_output(f"[color=ff3300]Статистика для {nickname} не найдена[/color]")
        
        except Exception as e:
            self.update_output(f"[color=ff3300]Ошибка: {str(e)}[/color]")
            logger.error(f"Ошибка обработки данных игрока {nickname}: {str(e)}")
    
    def _get_player_data(self, nickname):
        """Получает данные об игроке по API Faceit"""
        url = f"{BASE_URL}/players?nickname={nickname}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
                
            if response.status_code == 404:
                return None
                
            logger.warning(f"Ошибка API: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка запроса данных игрока: {str(e)}")
            return None

    def _get_stats_data(self, player_id, game_id):
        """Получает статистику игрока по API Faceit"""
        url = f"{BASE_URL}/players/{player_id}/stats/{game_id}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
                
            logger.warning(f"Ошибка API статистики: {response.status_code} - {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка запроса статистики: {str(e)}")
            return None
    
    def _calculate_avg_stats(self, lifetime, segments, game_id):
        """Улучшенный и более агрессивный поиск убийств и смертей"""
        # Безопасное извлечение числовых значений
        def safe_number(value, default=0):
            if value is None:
                return default
            try:
                # Удаляем все нечисловые символы, кроме точки
                if isinstance(value, str):
                    value = ''.join(c for c in value if c.isdigit() or c == '.')
                return int(float(value)) if value else default
            except (ValueError, TypeError):
                return default
        
        # Переменные для суммирования из сегментов
        match_count = 0
        kills_count = 0
        deaths_count = 0
        
        # Перебираем все сегменты и суммируем их значения
        for segment in segments:
            if 'stats' in segment:
                stats = segment.get('stats', {})
                segment_name = segment.get('label', 'Неизвестный')
                
                try:
                    # Пытаемся извлечь число матчей
                    matches_keys = ['Matches', 'Games']
                    segment_matches = 0
                    for key in matches_keys:
                        if key in stats:
                            segment_matches = safe_number(stats.get(key))
                            if segment_matches > 0:
                                break
                    
                    # Пытаемся извлечь убийства разными способами
                    kill_keys = ['Kills', 'K', 'Total Kills', 'Frags']
                    segment_kills = 0
                    for key in kill_keys:
                        if key in stats:
                            segment_kills = safe_number(stats.get(key))
                            if segment_kills > 0:
                                break
                    
                    # Пытаемся извлечь смерти разными способами
                    death_keys = ['Deaths', 'D', 'Total Deaths']
                    segment_deaths = 0
                    for key in death_keys:
                        if key in stats:
                            segment_deaths = safe_number(stats.get(key))
                            if segment_deaths > 0:
                                break
                    
                    if segment_matches > 0:
                        match_count += segment_matches
                        kills_count += segment_kills
                        deaths_count += segment_deaths
                except Exception as e:
                    logger.error(f"Ошибка при обработке сегмента '{segment_name}': {e}")
        
        # Выбор лучшего результата из доступных данных
        total_matches = 0
        total_kills = 0
        total_deaths = 0
        
        # Используем значения из сегментов, если там данные полнее
        if match_count > 0 and kills_count > 0:
            total_matches = match_count
            total_kills = kills_count
            total_deaths = deaths_count
        else:
            # Если в сегментах нет данных, используем lifetime
            if 'Matches' in lifetime:
                total_matches = safe_number(lifetime.get('Matches'))
            
            # Пробуем найти K/D и вычислить киллы через K/D и смерти
            if 'Average K/D Ratio' in lifetime and total_matches > 0:
                kd = float(lifetime.get('Average K/D Ratio', '0'))
                
                # Если есть смерти и K/D, можем оценить киллы
                if 'Deaths' in lifetime or 'Total Deaths' in lifetime:
                    deaths_val = lifetime.get('Deaths', lifetime.get('Total Deaths', 0))
                    total_deaths = safe_number(deaths_val)
                    
                    # Оцениваем киллы через K/D
                    total_kills = int(kd * total_deaths)
        
        # Расчет средних значений
        if total_matches > 0:
            avg_kills = f"{total_kills / total_matches:.1f}" if total_kills > 0 else "Н/Д"
            avg_deaths = f"{total_deaths / total_matches:.1f}" if total_deaths > 0 else "Н/Д"
        else:
            avg_kills = "Н/Д"
            avg_deaths = "Н/Д"
        
        return avg_kills, avg_deaths, total_matches, total_kills, total_deaths
    
    def _analyze_maps(self, segments, game_id):
        """
        Анализирует статистику по картам, используя готовые данные из API
        вместо повторного расчета средних значений
        """
        map_stats = []
        
        # Анализируем каждый сегмент (карту)
        for segment in segments:
            # Если это не карта, а другой тип сегмента - пропускаем
            if not segment.get("label") or "stats" not in segment:
                continue
                
            map_name = segment.get("label", "Unknown")
            map_data = segment.get("stats", {})
            
            try:
                matches = int(map_data.get("Matches", 0))
                if matches >= 3:  # Минимум 3 матча для статистики
                    # Сначала пробуем найти готовые средние значения в API
                    avg_kills_str = map_data.get("Average Kills", "")
                    
                    # Если готовых данных нет, используем наш расчет
                    if not avg_kills_str:
                        map_kills = int(map_data.get("Total Kills", 0))
                        map_avg_kills = map_kills / matches if matches > 0 else 0
                    else:
                        # Используем готовые данные из API
                        map_avg_kills = float(avg_kills_str)
                    
                    # Получаем K/D и винрейт
                    win_rate = int(map_data.get("Win Rate %", 0))
                    kd_str = map_data.get("Average K/D Ratio", "0")
                    avg_kd = float(kd_str) if kd_str and kd_str != "0" else 0
                    
                    # Рейтинг карты (60% винрейт + 40% К/Д)
                    map_rating = (win_rate * 0.6) + (avg_kd * 40)
                    
                    map_stats.append({
                        "name": map_name,
                        "matches": matches,
                        "win_rate": win_rate,
                        "kd": avg_kd,
                        "avg_kills": map_avg_kills,
                        "rating": map_rating
                    })
            except Exception as e:
                logger.error(f"Ошибка при анализе карты {map_name}: {e}")
        
        # Определение лучшей и худшей карт
        best_map = None
        worst_map = None
        
        if map_stats:
            sorted_maps = sorted(map_stats, key=lambda x: x["rating"], reverse=True)
            
            if sorted_maps:
                best_map = sorted_maps[0]
                
            if len(sorted_maps) > 1:
                worst_map = sorted_maps[-1]
        
        return best_map, worst_map
    
    def _format_and_display_stats(self, player_data, stats_data):
        """Форматирует и отображает статистику игрока"""
        try:
            nickname = player_data.get("nickname", "Н/Д")
            country_code = player_data.get("country", "Н/Д")
            
            # Преобразуем код страны в полное название
            country_name = get_country_name(country_code)
            
            games = player_data.get("games", {}).get("csgo", {}) or player_data.get("games", {}).get("cs2", {}) or {}
            skill_level = games.get("skill_level", "Н/Д")
            faceit_elo = games.get("faceit_elo", "Н/Д")
            
            lifetime = stats_data.get("lifetime", {})
            segments = stats_data.get("segments", [])
            
            # Определяем игру на основе полученных данных
            game_name = "CS:2"
            game_id = "cs2"
            
            if segments and "game" in segments[0]:
                if segments[0]["game"] == "csgo":
                    game_name = "CS:GO"
                    game_id = "csgo"
                    # Показываем сообщение если это CS:ГО данные
                    self.update_output(f"Статистика CS:2 для игрока {nickname} не найдена.\nПоказаны данные CS:GO вместо CS:2.")
                    return
                    
            # Расчет средних значений
            avg_kills, avg_deaths, total_matches, total_kills, total_deaths = self._calculate_avg_stats(lifetime, segments, game_id)
            
            # Анализ карт
            best_map, worst_map = self._analyze_maps(segments, game_id)
            
            # Длинный разделитель блоков
            line_separator = "\n[color=ff5500]" + "-" * 80 + "[/color]\n\n"
            
            # === БЛОК 1: Основная информация ===
            stats_text = f">> ИГРОК: [color=ff5500]{nickname}[/color]\n"
            stats_text += f"СТРАНА: [color=ff5500]{country_name}[/color]\n"  # Используем country_name вместо country
            stats_text += f"УРОВЕНЬ: [color=ff5500]{skill_level}[/color]\n"
            stats_text += f"ИГРА: [color=ff5500]{game_name}[/color]\n"
            stats_text += f"МАТЧЕЙ СЫГРАНО: [color=ff5500]{total_matches}[/color]\n"
            
            # Форматирование чисел с разделителями тысяч
            formatted_kills = f"{total_kills:,}".replace(',', ' ')
            formatted_deaths = f"{total_deaths:,}".replace(',', ' ')

            # И использовать их в выводе:
            stats_text += f"ВСЕГО УБИЙСТВ: [color=ff5500]{formatted_kills}[/color]\n"
            stats_text += f"ВСЕГО СМЕРТЕЙ: [color=ff5500]{formatted_deaths}[/color]\n"

            # Разделитель
            stats_text += line_separator
            
            # === БЛОК 2: Детальная статистика ===
            stats_text += f"ELO: [color=ff5500]{faceit_elo}[/color]\n"
            stats_text += f"K/D: [color=ff5500]{lifetime.get('Average K/D Ratio', 'Н/Д')}[/color]\n"
            stats_text += f"AVG KILLS: [color=ff5500]{avg_kills}[/color]\n"
            stats_text += f"AVG DEATHS: [color=ff5500]{avg_deaths}[/color]\n"
            stats_text += f"ХЕДШОТЫ: [color=ff5500]{lifetime.get('Average Headshots %', 'Н/Д')}[/color]%\n"
            stats_text += f"ТЕКУЩАЯ СЕРИЯ: [color=ff5500]{lifetime.get('Current Win Streak', 'Н/Д')} побед[/color]\n"
            stats_text += f"РЕКОРДНАЯ СЕРИЯ: [color=ff5500]{lifetime.get('Longest Win Streak', 'Н/Д')} побед[/color]\n"
            
            # Разделитель
            stats_text += line_separator
            
            # === БЛОК 3: Статистика карт ===
            stats_text += "КАРТЫ:\n\n"
            
            # Лучшая карта
            if best_map:
                stats_text += f"ЛУЧШАЯ: [color=ff5500]{best_map['name']}[/color]\n"
                stats_text += f"• Матчей: {best_map['matches']}\n"
                stats_text += f"• Винрейт: {best_map['win_rate']}%\n"
                stats_text += f"• K/D: {best_map['kd']:.2f}\n"
                stats_text += f"• Средние киллы: {best_map['avg_kills']:.1f}\n\n"
            else:
                stats_text += "ЛУЧШАЯ: [color=aaaaaa]недостаточно данных[/color]\n\n"
            
            # Худшая карта
            if worst_map:
                stats_text += f"ХУДШАЯ: [color=ff3300]{worst_map['name']}[/color]\n"
                stats_text += f"• Матчей: {worst_map['matches']}\n"
                stats_text += f"• Винрейт: {worst_map['win_rate']}%\n"
                stats_text += f"• K/D: {worst_map['kd']:.2f}\n"
                stats_text += f"• Средние киллы: {worst_map['avg_kills']:.1f}\n"
            else:
                stats_text += "ХУДШАЯ: [color=aaaaaa]недостаточно данных[/color]\n"
            
            self.update_output(stats_text)
            
        except Exception as e:
            self.update_output(f"[color=ff3300]Ошибка при обработке данных: {str(e)}[/color]")
            logger.error(f"Ошибка форматирования данных: {str(e)}")
    
    def update_output(self, text):
        """Обновляет текст вывода в основном потоке приложения"""
        from kivy.clock import Clock
        def update(dt):
            self.output_text = text
        Clock.schedule_once(update, 0)

def get_country_name(country_code):
    """Преобразует код страны в полное название с использованием API"""
    try:
        url = f"https://restcountries.com/v3.1/alpha/{country_code}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # Пытаемся найти русское название в переводах
            if 'translations' in data[0] and 'rus' in data[0]['translations']:
                return data[0]['translations']['rus']['common']
            # Если нет русского названия, используем английское
            return data[0]['name']['common']
        else:
            return country_code
    except Exception as e:
        logger.error(f"Ошибка при получении названия страны: {e}")
        return country_code

# Дизайн интерфейса остаётся без изменений
KV = """
<MatrixButton@Button>:
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: (1, 0.33, 0, 1) if self.state == 'normal' else (1, 0.5, 0, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [15, 15, 15, 15]  # Увеличенный радиус для большего закругления
        # Добавим обводку
        Color:
            rgba: (1, 0.33, 0, 1) if self.state == 'normal' else (1, 0.5, 0, 1)
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, 15]
            width: 1.5
    font_size: '16sp'
    bold: True
    color: 1, 1, 1, 1  # Изменяем на белый цвет для лучшей видимости
    padding: [15, 10]

<StatsLayout>:
    orientation: "vertical"
    padding: "10dp"
    spacing: 0
    canvas.before:
        Color:
            rgba: 0, 0, 0, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Заголовок
    Label:
        text: "> FACEIT ANALYZE <"
        font_size: '22sp'
        bold: True
        color: 1, 0.33, 0, 1
        halign: "center"
        valign: "middle"
        size_hint_y: None
        height: "40dp"
    
    # Поле ввода
    BoxLayout:
        size_hint_y: None
        height: "50dp"
        orientation: "horizontal"
        spacing: "10dp"
        
        TextInput:
            id: nickname_input
            multiline: False
            hint_text: "Введите никнейм игрока или ссылку на профиль"
            background_color: 0.1, 0.05, 0.02, 1
            foreground_color: 1, 0.33, 0, 1
            cursor_color: 1, 0.33, 0, 1
            font_size: '16sp'
            padding: [15, 12]
            on_text_validate: root.fetch_stats(self.text)
            size_hint_x: 0.7
            size_hint_y: None
            height: "50dp"
            
            # Отключаем прокрутку
            do_wrap: False
            do_scroll_x: False
            do_scroll_y: False
            scroll_x: 0
            scroll_y: 1
            
            input_filter: lambda text, from_undo: text[:50]

        MatrixButton:
            text: "SCAN"
            size_hint_x: 0.3
            size_hint_y: None
            height: "50dp"
            on_press: root.fetch_stats(nickname_input.text)

    # Область вывода
    ScrollView:
        do_scroll_x: False
        bar_width: 10
        bar_color: 1, 0.33, 0, 0.7
        bar_inactive_color: 0.4, 0.2, 0, 0.2
        effect_cls: "ScrollEffect"
        scroll_y: 1
        
        Label:
            text: root.output_text if root.output_text != "_" else ""
            text_size: self.width - 20, None
            size_hint_y: None
            height: max(self.texture_size[1], 400)
            halign: "left"
            valign: "top"
            padding: [20, 20]
            color: 1, 0.33, 0, 1
            markup: True
            line_height: 1.1
    
    # Подвал
    Label:
        size_hint_y: None
        height: "15dp"
        text: "© 2025 FACEIT_TRACKER_SYSTEM v1.0"
        font_size: '10sp'
        color: 0.7, 0.3, 0, 0.7
        halign: "center"
"""

# Основной класс приложения
class FaceitAnalyzeApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Установка иконки для окна Kivy и для Windows
        self.icon = icon_path
        self.title = 'FACEIT ANALYZE'
        
    @staticmethod
    def resource_path(relative_path):
        """Получает абсолютный путь к ресурсу, работает как в упакованной, так и в обычной версии"""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        return os.path.join(base_path, relative_path)
    
    def build(self):
        # Настройка иконки для окна и для приложения
        self.icon = icon_path
        
        # Явно устанавливаем иконку для окна
        try:
            Window.set_icon(icon_path)
        except Exception as e:
            logger.error(f"Ошибка установки иконки для окна: {e}")
        
        Builder.load_string(KV)
        return StatsLayout()

# Запуск приложения
if __name__ == "__main__":
    # Регистрация AppUserModelID для Windows
    if os.name == 'nt':  # Windows
        try:
            import ctypes
            app_id = 'faceitanalyze.cs2.v1.0'  # Используем идентификатор без точек и пробелов
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            
            # Дополнительная регистрация для .exe файлов
            if getattr(sys, 'frozen', False):
                import win32con
                import win32gui
                import win32api
                hwnd = win32gui.GetForegroundWindow()
                icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
                try:
                    hicon = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, 0, 0, icon_flags)
                    win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
                    win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon)
                except Exception as e:
                    print(f"Ошибка установки иконки Windows: {e}")
        except Exception as e:
            print(f"Ошибка регистрации идентификатора приложения: {e}")
    
    # Запуск приложения
    FaceitAnalyzeApp().run()