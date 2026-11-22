# Hisaab: 2-minute demo script

Pitch: "Other apps make you type the past. Hisaab you just talk to, and it tells you the future."

Setup before recording: open the web app on a phone-width window (390px) at https://hisaab-peach-phi.vercel.app. Open https://hisaab-api-q5n9.onrender.com/health a minute before, because the free API sleeps. Use the seed data. DEMO_TODAY is pinned on Render so the figures match every take. Open the SMS simulator in a second tab at https://hisaab-peach-phi.vercel.app/sms-simulator. Have the mic bar ready. Every figure on screen comes from the API. Do not quote a number from memory.

## Timing

| Time | Step |
|---|---|
| 0:00 | 1. Hook |
| 0:12 | 2. Home shortfall card |
| 0:28 | 3. Voice: will I manage rent |
| 0:48 | 4. Voice: what if Kabir pays late |
| 1:08 | 5. SMS simulator: Rohan pays |
| 1:28 | 6. Home updates live |
| 1:40 | 7. Who to chase today, and WhatsApp |
| 1:58 | 8. Business model |

## 1. Hook (0:00)

Say: "Other apps make you type the past. Hisaab you just talk to, and it tells you the future."
Show: the Home screen.
Typed fallback: none needed; this step is spoken only.

## 2. Home shortfall card (0:12)

Say: "Priya has 40 students. Rent is Rs 12,000 on the 1st. Hisaab shows her, before it happens, when she runs short and by how much."
Show: the red shortfall card on Home, which reads "You'll be [amount] short on [date]" when there is a shortfall.
Typed fallback: none needed; the card is on screen.

## 3. Voice: will I manage rent (0:28)

Say: "Will I manage rent next month?"
Show: the mic bar answer. It should use the forecast intent and name the shortfall, if there is one, with its date and amount.
Typed fallback: type "Will I manage rent next month?" into the mic bar in place of speaking it.

## 4. Voice: what if Kabir is late (0:48)

Say: "What if Kabir pays 15 days late?"
Show: the reply and the what-if line on the forecast chart, moving down between the days Kabir's fee is delayed.
Typed fallback: type "What if Kabir pays 15 days late?" into the mic bar.

## 5. SMS simulator: Rohan pays (1:08)

Say: "Now a bank text arrives. Rohan has paid."
Show: switch to the second tab at /sms-simulator. Choose the preset "Rohan pays (known UPI id)" and press "Send SMS". The preset message is "Rs 3,000.00 credited to A/c XX1234 ... by VPA rohan.sharma@okaxis (UPI Ref No ...)".
Typed fallback: paste the same message into the "Or paste any bank SMS here" box, then press "Send SMS".

## 6. Home updates live (1:28)

Say: "Hisaab matched it to Rohan's open invoice, and the forecast has moved."
Show: back on Home. The page refreshes every 5 seconds, so the balance and the shortfall card update without a reload. Wait up to 5 seconds if it has not changed yet.
Typed fallback: press reload on Home.

## 7. Who to chase today, and WhatsApp (1:40)

Say: "Who should I chase today?"
Show: the mic bar reply naming the customers to chase, and the Home action card with the total and whether it covers the shortfall. Tap the WhatsApp reminder. It opens WhatsApp with the message filled in. Nothing is sent automatically.
Typed fallback: type "Who should I chase today?" into the mic bar, then tap the WhatsApp reminder on the Home action card.

## 8. Business model (1:58)

Say: "Hisaab is for home tutors and small service businesses, who manage cash in their head today. The product is free to try, and the business model is [PRICING AND MODEL TO BE FILLED IN BY THE TEAM]."
Show: the Home screen.
Note: the repo contains no pricing. Leave the bracketed placeholder exactly as written. Do not invent a price.

## Notes for the presenter

- If the shortfall figures look wrong, check DEMO_TODAY first. Figures change when the date changes.
- The voice agent is rule-based. Stick to the exact phrases above. If a phrase is not understood, use its typed fallback.
- All data is synthetic.
