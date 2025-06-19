import unittest
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rss_monitor import TestExceptionHandling, TestInputValidation

if __name__ == '__main__':
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты для обработки исключений
    suite.addTests(loader.loadTestsFromTestCase(TestExceptionHandling))
    
    # Добавляем тесты для валидации входных данных
    suite.addTests(loader.loadTestsFromTestCase(TestInputValidation))
    
    # Запускаем тесты с подробным выводом
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Выводим статистику
    print(f"\n{'='*50}")
    print(f"Всего тестов: {result.testsRun}")
    print(f"Успешных: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Ошибок: {len(result.errors)}")
    print(f"Неудач: {len(result.failures)}")
    print(f"{'='*50}")
    
    # Завершаем с кодом ошибки если есть неудачи
    sys.exit(0 if result.wasSuccessful() else 1)