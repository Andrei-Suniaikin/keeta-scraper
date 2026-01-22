from playwright.sync_api import sync_playwright
import time


SUCCESS_URL_PART = "index.html"
AUTH_FILE = "auth.json"

def save_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("🔵 Открываю страницу входа...")
        page.goto("https://merchant-eu.mykeeta.com/")

        print("🔑 Пожалуйста, введите логин и пароль в открывшемся браузере.")
        print("⏳ Я жду, пока вы успешно войдете в систему...")

        while True:
            if SUCCESS_URL_PART in page.url:
                print("✅ Вижу, что URL изменился на внутренний!")
                break

            cookies = context.cookies()
            cookie_names = [c['name'] for c in cookies]


            if 'token' in cookie_names or 'user_ticket' in cookie_names:
                print("✅ Вижу куки авторизации!")
                break

            if page.is_closed():
                print("❌ Окно браузера было закрыто пользователем до завершения!")
                return

            time.sleep(2)

        print("💾 Сохраняю сессию в файл...")

        page.wait_for_timeout(10000)

        context.storage_state(path=AUTH_FILE)
        print(f"🎉 Готово! Файл {AUTH_FILE} успешно записан.")
        print("Теперь можете запускать основного бота.")

        browser.close()

if __name__ == "__main__":
    save_session()