import unittest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, Mock, MagicMock
from flask import Flask

# Добавляем путь к основному модулю
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rss_monitor import RSSMonitor, app

class TestExceptionHandling(unittest.TestCase):
    """
    Тесты для Issue #2: Отсутствие обработки исключений
    Используемые приемы тестирования из "Совершенный код" гл. 22.3:
    """
    
    def setUp(self):
        """Подготовка тестовых данных"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.monitor = RSSMonitor(self.temp_db.name)
    
    def tearDown(self):
        """Очистка после тестов"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_init_db_with_invalid_path(self):
        """
        Прием: Тестирование граничных условий - некорректный путь к БД
        Проверяем поведение при невозможности создать БД
        """
        invalid_path = "/root/restricted/invalid.db"
        with self.assertRaises((sqlite3.OperationalError, PermissionError)):
            monitor = RSSMonitor(invalid_path)
    
    def test_init_db_with_readonly_path(self):
        """
        Прием: Тестирование ошибочных данных - БД только для чтения
        """
        # Создаем readonly файл
        readonly_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        readonly_db.close()
        os.chmod(readonly_db.name, 0o444)  # Только чтение
        
        try:
            with self.assertRaises(sqlite3.OperationalError):
                monitor = RSSMonitor(readonly_db.name)
                monitor.init_db()
        finally:
            os.chmod(readonly_db.name, 0o644)
            os.unlink(readonly_db.name)
    
    @patch('sqlite3.connect')
    def test_get_active_feeds_db_connection_error(self, mock_connect):
        """
        Прием: Тестирование с использованием mock объектов
        Моделируем ошибку подключения к БД
        """
        mock_connect.side_effect = sqlite3.Error("Database connection failed")
        
        with self.assertRaises(sqlite3.Error):
            self.monitor.get_active_feeds()
    
    @patch('sqlite3.connect')
    def test_get_active_keywords_cursor_error(self, mock_connect):
        """
        Прием: Тестирование исключительных ситуаций - ошибка выполнения запроса
        """
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Query execution failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with self.assertRaises(sqlite3.Error):
            self.monitor.get_active_keywords()
    
    @patch('feedparser.parse')
    def test_parse_feed_network_error(self, mock_parse):
        """
        Прием: Тестирование внешних зависимостей - сетевая ошибка
        """
        mock_parse.side_effect = Exception("Network timeout")
        
        # Тест не должен падать, а логировать ошибку
        try:
            self.monitor.parse_feed("Test Feed", "http://invalid.url", ["test"])
        except Exception as e:
            self.fail(f"parse_feed должен обрабатывать сетевые ошибки, но упал с: {e}")
    
    @patch('feedparser.parse')
    def test_parse_feed_malformed_xml(self, mock_parse):
        """
        Прием: Тестирование некорректных входных данных - поврежденный XML
        """
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("XML parsing error")
        mock_feed.entries = []
        mock_parse.return_value = mock_feed
        
        # Должно обрабатываться без падения
        self.monitor.parse_feed("Test Feed", "http://test.url", ["keyword"])
        # Проверяем, что вызов не привел к исключению
        self.assertTrue(True)
    
    def test_clean_html_with_none_input(self):
        """
        Прием: Тестирование граничных значений - None входные данные
        """
        result = self.monitor.clean_html(None)
        self.assertEqual(result, "")
    
    def test_clean_html_with_empty_string(self):
        """
        Прием: Тестирование пустых значений - пустая строка
        """
        result = self.monitor.clean_html("")
        self.assertEqual(result, "")


class TestInputValidation(unittest.TestCase):
    """
    Тесты для Issue #5: Отсутствие валидации входных данных
    """
    
    def setUp(self):
        """Подготовка тестового приложения Flask"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Создаем временную БД для тестов
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
    
    def tearDown(self):
        """Очистка после тестов"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_add_feed_with_empty_name(self):
        """
        Прием: Тестирование граничных условий - пустое имя фида
        """
        response = self.client.post('/add_feed', data={
            'name': '',
            'url': 'https://example.com/feed.xml'
        })
        # Приложение должно обрабатывать это корректно
        self.assertEqual(response.status_code, 302)  # Редирект
    
    def test_add_feed_with_none_name(self):
        """
        Прием: Тестирование NULL значений - отсутствующее имя
        """
        response = self.client.post('/add_feed', data={
            'url': 'https://example.com/feed.xml'
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_feed_with_invalid_url_format(self):
        """
        Прием: Тестирование некорректных данных - неправильный формат URL
        """
        response = self.client.post('/add_feed', data={
            'name': 'Test Feed',
            'url': 'not-a-valid-url'
        })
        # Должно обрабатываться без ошибок сервера
        self.assertIn(response.status_code, [200, 302, 400])
    
    def test_add_feed_with_extremely_long_name(self):
        """
        Прием: Тестирование граничных значений - слишком длинное имя
        """
        long_name = 'A' * 10000  # Очень длинное имя
        response = self.client.post('/add_feed', data={
            'name': long_name,
            'url': 'https://example.com/feed.xml'
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_empty_value(self):
        """
        Прием: Тестирование пустых значений - пустое ключевое слово
        """
        response = self.client.post('/add_keyword', data={
            'keyword': ''
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_special_characters(self):
        """
        Прием: Тестирование спецсимволов - ключевое слово со спецсимволами
        """
        special_keyword = '"><script>alert("xss")</script>'
        response = self.client.post('/add_keyword', data={
            'keyword': special_keyword
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_unicode_characters(self):
        """
        Прием: Тестирование интернационализации - Unicode символы
        """
        unicode_keyword = 'тест 测试 🔍'
        response = self.client.post('/add_keyword', data={
            'keyword': unicode_keyword
        })
        self.assertEqual(response.status_code, 302)
    
    def test_check_keywords_in_text_with_none_input(self):
        """
        Прием: Тестирование NULL входных данных
        """
        monitor = RSSMonitor(self.temp_db.name)
        result = monitor.check_keywords_in_text(None, ['test'])
        self.assertEqual(result, [])


if __name__ == '__main__':
    # Запуск всех тестов
    unittest.main(verbosity=2)