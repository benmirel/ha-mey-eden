# Mei Eden Israel Integration for Home Assistant 💧

A custom Home Assistant integration to track your **Mei Eden (מי עדן)** water delivery account, consumption statistics, balance, and upcoming deliveries.

This integration connects directly to the Mei Eden customer portal securely using one-time SMS verification. No passwords are stored.

---

## 📊 Features & Sensors

The integration automatically creates a device for your account with the following sensors:

* 🚚 **Next Delivery & Second Next Delivery** – Full date sensors tracking your upcoming water shipments. Home Assistant will automatically display these as "Tomorrow", "In 3 days", etc.
* 📊 **Estimated Delivery Volume (Liters)** – Automatically calculates the expected water volume for your next delivery by averaging your last 3 months of consumption history and scaling it based on your delivery frequency. Works seamlessly for 11L bottles, 19L bottles, or standard packs.
* 💰 **Account Balance** – Monitors your current outstanding balance in Israeli New Shekels (₪).
* 📅 **Delivery Frequency** – Displays the fixed cycle interval of your deliveries (in weeks).
* 🏡 **Delivery Address** – Shows the official formatted delivery address associated with your subscription.
* 🔐 **Account Status** – Tracks whether your subscription is Active, Suspended, or Closed.

---

## 🛠️ Installation via HACS (Recommended)

1. Open **HACS** in your Home Assistant dashboard.
2. Navigate to **Integrations**.
3. Click the **3 dots** in the top right corner and select **Custom repositories**.
4. Paste the repository URL: `https://github.com/benmirel/ha-mey-eden`
5. Select **Integration** as the category and click **Add**.
6. Find the **Mei Eden Israel** integration in HACS and click **Download**.
7. **Restart Home Assistant** to load the custom component files.

---

## 🚀 Configuration

1. Go to **Settings** ➡️ **Devices & Services**.
2. Click the **+ Add Integration** button in the bottom right.
3. Search for **Mei Eden Israel** and select it.
4. Enter your registered phone number (Format: `05XXXXXXXX`).
5. You will receive a one-time verification code via SMS. Enter the code in the prompt.
6. Your account device and all sensors will be created instantly!

---

## 📄 Disclaimer

This integration is an independent open-source project and is **not** officially affiliated with, endorsed by, or connected to Mei Eden (Maayanot Eden Ltd.). Use it at your own discretion.
