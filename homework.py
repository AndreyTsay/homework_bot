import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Updater

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

updater = Updater(token=TELEGRAM_TOKEN)
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Функция проверки токена."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Функция отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения {error}')
    logging.debug(f'Сообщение"{message}" отправленно')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            dict(url=ENDPOINT, headers=HEADERS, params=params))
    except requests.exceptions.RequestException as error:
        raise telegram.TelegramError(
            f'Ошибка подключения {error}')
    response_status = response.status_code
    if response_status != 200:
        raise KeyError(f'Endpoint не доступен {response_status}')
    return response.json()


def check_response(response):
    """Функция провреки ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует компонент "homeworks" в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не является списком')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Ответ API не содержит ключа "homework_name"')
    homework_status = homework.get('status')
    if not homework_status:
        raise KeyError('Ответ API не содержит ключа "homework_status"')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise KeyError(f'Неизвестный статус "{homework_status}" '
                       f'у работы "{homework_name}"')
    verdict = HOMEWORK_VERDICTS[homework_status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise logging.critical('Отсутствуют обязательные переменные окружения.'
                               'Программа остановлена!')

    bot = Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Запуск Бота')
    current_timestamp = int(time.time())
    last_message_cache = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                if message != '':
                    send_message(bot, message)
            current_timestamp = int(time.time())
        except IndexError:
            logging.error('Формат не соответсвует JSON')
        except Exception as error:
            message = f'{error}'
            logging.error(message)
            if message != last_message_cache:
                send_message(bot, message)
                last_message_cache = message
        finally:
            time.sleep(RETRY_PERIOD)
        logging.info(f'Сообщение {message} отправлено')


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(message)s, %(lineno)d, %(name)s',
        filemode='w',
        filename='LOG.log',
        level=logging.INFO,
    )
    main()
