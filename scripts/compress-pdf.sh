# --- Telegram (optional) ---
TOKEN="YOUR_TOKEN_HERE"
CHAT_ID="YOUR_CHAT_ID_HERE"
SOURCE="downloads_part1"
DEST="compressed_pdf"

# Send a message to Telegram
send_tg() {
	curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
		-d chat_id="$CHAT_ID" \
		-d text="$1" >/dev/null
}

# 1. Mirror directory structure
echo "Checking folder structure..."
find "$SOURCE" -type d | while read -r dir; do
	mkdir -p "${dir/$SOURCE/$DEST}"
done

# 2. Count PDFs
total_files=$(find "$SOURCE" -name "*.pdf" -type f | wc -l | xargs)
current=0

if [ "$total_files" -eq 0 ]; then
	send_tg "⚠️ Error: no PDF files found in $SOURCE"
	exit 1
fi

# --- Start notification ---
send_tg "🚀 Starting batch compression.
📂 Folder: $SOURCE
🔢 Total files: $total_files
⚙️ Setting: extreme compression (/screen)"

# 3. Main loop
find "$SOURCE" -name "*.pdf" -type f | while read -r f; do
	((current++))

	out_file="${f/$SOURCE/$DEST}"

	# Skip already compressed (resume)
	if [ -f "$out_file" ]; then
		continue
	fi

	# Ghostscript compression
	if gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/screen \
		-dNOPAUSE -dQUIET -dBATCH \
		-sOutputFile="$out_file" "$f"; then

		# Progress notification every 1000 files
		if ((current % 1000 == 0)); then
			send_tg "📊 Progress: $current of $total_files files done..."
		fi
	else
		send_tg "❌ Error in file: ${f##*/}"
	fi

	# Console progress
	percent=$((current * 100 / total_files))
	echo -ne "\rProgress: $percent% [$current/$total_files] Compressing: ${f##*/} \033[K"
done

# --- Done notification ---
send_tg "✅ Compression finished.
🏁 Files processed: $total_files
📂 Output folder: $DEST"

echo -e "\nDone."
