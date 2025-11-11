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

        # Разбиваем на пачки по 50 стикеров
        batch_size = 50
        all_stickers = original_set.stickers
        
        # ПАЧКА 1: Создаем пак с первыми 50 стикерами
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

        await msg.edit_text(f"✅ Создан пак с первыми 50 стикерами\nДобавляю остальные...")

        # ПАЧКА 2: Стикеры 51-100 (если есть)
        if total_stickers > batch_size:
            second_batch = all_stickers[batch_size:batch_size * 2]
            second_batch_stickers = []
            
            for sticker in second_batch:
                emoji = sticker.emoji or "👍"
                second_batch_stickers.append(
                    InputSticker(
                        sticker=sticker.file_id,
                        emoji_list=[emoji],
                        format=sticker_format
                    )
                )
            
            # Добавляем вторую пачку
            for sticker_obj in second_batch_stickers:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj
                )
            
            current_count = min(batch_size * 2, total_stickers)
            await msg.edit_text(f"✅ Добавлено {current_count}/120 стикеров\nПродолжаю...")

        # ПАЧКА 3: Стикеры 101-120 (если есть)
        if total_stickers > batch_size * 2:
            third_batch = all_stickers[batch_size * 2:]
            third_batch_stickers = []
            
            for sticker in third_batch:
                emoji = sticker.emoji or "👍"
                third_batch_stickers.append(
                    InputSticker(
                        sticker=sticker.file_id,
                        emoji_list=[emoji],
                        format=sticker_format
                    )
                )
            
            # Добавляем третью пачку
            for sticker_obj in third_batch_stickers:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_name,
                    sticker=sticker_obj
                )

        await msg.edit_text(f"✅ t.me/addstickers/{new_name}\nСтикеров: {total_stickers}/120")

    except TelegramBadRequest as e:
        if "sticker set name is already taken" in str(e):
            await msg.edit_text("❌ Имя занято")
        elif "STICKERSET_INVALID" in str(e):
            await msg.edit_text("❌ Пак не найден")
        else:
            await msg.edit_text(f"❌ Ошибка: {e}")
    
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

    await state.clear()