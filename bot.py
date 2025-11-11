@dp.message(CopyPack.waiting_for_new_name)
async def get_new_name_and_copy(message: Message, state: FSMContext):
    user_data = await state.get_data()
    original_set_name = user_data.get("original_set_name")
    new_name = message.text.strip()
    user_id = message.from_user.id

    me = await bot.get_me()
    new_name = new_name + f"_by_{me.username}"
    
    msg = await message.answer("Копирую...")

    try:
        original_set = await bot.get_sticker_set(original_set_name)
        total_stickers = len(original_set.stickers)

        # Определяем формат
        sticker_format = "static"
        if original_set.is_animated:
            sticker_format = "animated"
        elif original_set.is_video:
            sticker_format = "video"

        # Разбиваем на пачки по 10 стикеров (меньше = меньше запросов)
        batch_size = 10
        all_stickers = original_set.stickers
        
        # ПАЧКА 1: Создаем пак с первыми 10 стикерами
        first_batch = all_stickers[:batch_size]
        first_batch_stickers = []
        
        for sticker in first_batch:
            emoji = sticker.emoji or "👍"
            first_batch_stickers.append(
                InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=sticker_format
                )
            )

        await bot.create_new_sticker_set(
            user_id=user_id,
            name=new_name,
            title="ТГ Канал - @mupowkins",
            stickers=first_batch_stickers,
            sticker_format=sticker_format
        )

        await msg.edit_text(f"✅ Создан пак\nДобавляю остальные стикеры... {batch_size}/{total_stickers}")

        # Добавляем остальные стикеры пачками с задержками
        for i in range(batch_size, total_stickers, batch_size):
            batch = all_stickers[i:i + batch_size]
            
            for sticker in batch:
                emoji = sticker.emoji or "👍"
                sticker_obj = InputSticker(
                    sticker=sticker.file_id,
                    emoji_list=[emoji],
                    format=sticker_format
                )
                
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj
                )
                
                # ЗАДЕРЖКА МЕЖДУ КАЖДЫМ СТИКЕРОМ
                await asyncio.sleep(0.5)
            
            current_progress = min(i + batch_size, total_stickers)
            await msg.edit_text(f"✅ Добавлено {current_progress}/{total_stickers}")
            
            # ЗАДЕРЖКА МЕЖДУ ПАЧКАМИ
            await asyncio.sleep(2)

        await msg.edit_text(f"✅ t.me/addstickers/{new_name}\nСтикеров: {total_stickers}")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        elif "Flood control" in str(e) or "Too Many Requests" in str(e):
            await msg.edit_text("❌ Слишком много запросов. Подожди 10 секунд и попробуй снова.")
        else:
            await msg.edit_text(f"❌ Ошибка: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

    await state.clear()