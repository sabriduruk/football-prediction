"""
Futbol Tahmin Uygulamasi
========================
CustomTkinter ile modern masaustu uygulamasi.
"""

import customtkinter as ctk
from tkinter import messagebox
import pandas as pd
import threading
from typing import Dict, List, Optional
from datetime import datetime

from data_fetcher import fetch_all_data, SUPPORTED_LEAGUES, clear_cache, get_week_range
from predictor import MatchPredictor, predictions_to_dataframe, calculate_banko_score


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MatchCheckbox:
    """Tek bir mac icin checkbox widget'i."""
    
    def __init__(self, parent, match_data: dict, row: int):
        self.match_data = match_data
        self.var = ctk.BooleanVar(value=False)
        self.visible = True
        
        home = match_data.get('home_team', 'Home')[:18]
        away = match_data.get('away_team', 'Away')[:18]
        
        turkey_time = match_data.get('turkey_time', '')
        if turkey_time:
            date_str = f"TR {turkey_time}"
        else:
            date = match_data.get('match_date', '')
            if isinstance(date, pd.Timestamp):
                date_str = date.strftime('%d/%m %H:%M')
            else:
                date_str = str(date)[:10] if date else ''
        
        match_text = f"{home}  vs  {away}"
        
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
        self.frame.grid_columnconfigure(1, weight=1)
        
        self.checkbox = ctk.CTkCheckBox(
            self.frame,
            text="",
            variable=self.var,
            width=24,
            checkbox_width=20,
            checkbox_height=20
        )
        self.checkbox.grid(row=0, column=0, padx=(5, 10))
        
        self.label = ctk.CTkLabel(
            self.frame,
            text=match_text,
            font=ctk.CTkFont(size=13),
            anchor="w"
        )
        self.label.grid(row=0, column=1, sticky="w")
        
        self.date_label = ctk.CTkLabel(
            self.frame,
            text=date_str,
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.date_label.grid(row=0, column=2, padx=(10, 5))
    
    def is_selected(self) -> bool:
        return self.var.get()
    
    def set_selected(self, value: bool):
        self.var.set(value)
    
    def get_data(self) -> dict:
        return self.match_data
    
    def show(self):
        self.frame.grid()
        self.visible = True
    
    def hide(self):
        self.frame.grid_remove()
        self.visible = False
    
    def matches_search(self, search_text: str) -> bool:
        """Arama metnine uyuyor mu?"""
        if not search_text:
            return True
        search_lower = search_text.lower()
        home = self.match_data.get('home_team', '').lower()
        away = self.match_data.get('away_team', '').lower()
        return search_lower in home or search_lower in away


class LeagueSection:
    """Bir lig icin mac listesi bolumu."""
    
    def __init__(self, parent, league_name: str, league_display: str, matches: pd.DataFrame, start_row: int):
        self.league_name = league_name
        self.league_display = league_display
        self.match_checkboxes: List[MatchCheckbox] = []
        self.visible = True
        
        self.header = ctk.CTkLabel(
            parent,
            text=league_display,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#3B8ED0",
            anchor="w"
        )
        self.header.grid(row=start_row, column=0, sticky="ew", padx=10, pady=(15, 5))
        
        self.separator = ctk.CTkFrame(parent, height=2, fg_color="#3B8ED0")
        self.separator.grid(row=start_row + 1, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        current_row = start_row + 2
        for idx, match in matches.iterrows():
            checkbox = MatchCheckbox(parent, match.to_dict(), current_row)
            self.match_checkboxes.append(checkbox)
            current_row += 1
        
        self.end_row = current_row
    
    def select_all(self, value: bool):
        for cb in self.match_checkboxes:
            if cb.visible:
                cb.set_selected(value)
    
    def get_selected_matches(self) -> List[dict]:
        return [cb.get_data() for cb in self.match_checkboxes if cb.is_selected()]
    
    def filter_by_search(self, search_text: str) -> int:
        """Arama uygula ve gorunen mac sayisini dondur."""
        visible_count = 0
        for cb in self.match_checkboxes:
            if cb.matches_search(search_text):
                cb.show()
                visible_count += 1
            else:
                cb.hide()
        
        # Lig basligini gizle/goster
        if visible_count == 0:
            self.header.grid_remove()
            self.separator.grid_remove()
            self.visible = False
        else:
            self.header.grid()
            self.separator.grid()
            self.visible = True
        
        return visible_count


class FutbolTahminApp(ctk.CTk):
    """Ana uygulama penceresi."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Futbol Mac Tahmin Sistemi")
        self.geometry("1600x900")
        self.minsize(1400, 700)
        
        self.matches_df: Optional[pd.DataFrame] = None
        self.league_sections: Dict[str, LeagueSection] = {}
        self.all_checkboxes: List[MatchCheckbox] = []
        
        self._create_ui()
        self.after(500, self.load_fixtures_async)
    
    def _create_ui(self):
        """Tum UI bilesenlerini olustur."""
        
        self.grid_columnconfigure(0, weight=1, minsize=380)
        self.grid_columnconfigure(1, weight=3, minsize=900)
        self.grid_rowconfigure(1, weight=1)
        
        # UST PANEL
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 10))
        self.top_frame.grid_columnconfigure(1, weight=1)
        
        # Hafta bilgisi
        start_date, end_date = get_week_range()
        week_str = f"Hafta: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')} (Sali-Sali)"
        
        self.title_label = ctk.CTkLabel(
            self.top_frame,
            text=f"Futbol Mac Tahmin Sistemi\n{week_str}",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        
        self.button_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.button_frame.grid(row=0, column=2, sticky="e")
        
        self.update_data_btn = ctk.CTkButton(
            self.button_frame,
            text="Verileri Guncelle",
            command=self.update_data,
            width=130,
            fg_color="#8B4513",
            hover_color="#A0522D"
        )
        self.update_data_btn.grid(row=0, column=0, padx=3)
        
        self.select_all_btn = ctk.CTkButton(
            self.button_frame,
            text="Tumunu Sec",
            command=self.toggle_select_all,
            width=100,
            fg_color="#4A4A4A",
            hover_color="#5A5A5A"
        )
        self.select_all_btn.grid(row=0, column=1, padx=3)
        
        self.analyze_btn = ctk.CTkButton(
            self.button_frame,
            text="Analiz Et",
            command=self.run_analysis,
            width=100,
            fg_color="#1E5128",
            hover_color="#2E7138",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.analyze_btn.grid(row=0, column=2, padx=3)
        
        self.top10_btn = ctk.CTkButton(
            self.button_frame,
            text="En Garanti 10-14",
            command=self.select_top_guaranteed,
            width=130,
            fg_color="#4B0082",
            hover_color="#6A0DAD",
            state="disabled"
        )
        self.top10_btn.grid(row=0, column=3, padx=3)
        
        self.clear_btn = ctk.CTkButton(
            self.button_frame,
            text="Tabloyu Temizle",
            command=self.clear_results,
            width=120,
            fg_color="#8B0000",
            hover_color="#A52A2A"
        )
        self.clear_btn.grid(row=0, column=4, padx=3)
        
        # SOL PANEL
        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        self.left_frame.grid_rowconfigure(3, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)
        
        from datetime import date, timedelta
        today = date.today()
        self.left_header = ctk.CTkLabel(
            self.left_frame,
            text=f"Maclar ({today.strftime('%d/%m')} - {end_date.strftime('%d/%m')})",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.left_header.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        
        # SOL PANEL - Tarih Filtreleme Butonlari
        self.date_filter_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.date_filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        
        # "Tumu" butonu
        self.date_filter_var = ctk.StringVar(value="all")
        self.date_buttons = {}
        
        self.all_dates_btn = ctk.CTkButton(
            self.date_filter_frame,
            text="Tumu",
            width=50,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#1E5128",
            hover_color="#2E7138",
            command=lambda: self.filter_by_date("all")
        )
        self.all_dates_btn.pack(side="left", padx=2)
        self.date_buttons["all"] = self.all_dates_btn
        
        # Her gun icin buton olustur
        current_date = today
        while current_date < end_date:
            date_str = current_date.strftime('%d/%m')
            date_key = current_date.strftime('%Y-%m-%d')
            
            btn = ctk.CTkButton(
                self.date_filter_frame,
                text=date_str,
                width=50,
                height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#4A4A4A",
                hover_color="#5A5A5A",
                command=lambda d=date_key: self.filter_by_date(d)
            )
            btn.pack(side="left", padx=2)
            self.date_buttons[date_key] = btn
            
            current_date += timedelta(days=1)
        
        # SOL PANEL - Arama
        self.left_search_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.left_search_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.left_search_frame.grid_columnconfigure(1, weight=1)
        
        self.left_search_label = ctk.CTkLabel(
            self.left_search_frame,
            text="Takim Ara:",
            font=ctk.CTkFont(size=12)
        )
        self.left_search_label.grid(row=0, column=0, padx=(5, 5))
        
        self.left_search_var = ctk.StringVar()
        self.left_search_entry = ctk.CTkEntry(
            self.left_search_frame,
            textvariable=self.left_search_var,
            width=200,
            placeholder_text="Galatasaray, Barcelona...",
            font=ctk.CTkFont(size=12)
        )
        self.left_search_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.left_search_entry.bind('<KeyRelease>', self.on_left_search)
        
        self.matches_scroll = ctk.CTkScrollableFrame(
            self.left_frame,
            corner_radius=5,
            fg_color="transparent"
        )
        self.matches_scroll.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.matches_scroll.grid_columnconfigure(0, weight=1)
        
        self.loading_label = ctk.CTkLabel(
            self.matches_scroll,
            text="Fikstur yukleniyor...",
            font=ctk.CTkFont(size=14)
        )
        self.loading_label.grid(row=0, column=0, pady=50)
        
        # SAG PANEL
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        self.right_frame.grid_rowconfigure(2, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        
        # Sag panel ust cerceve
        self.right_top_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.right_top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.right_top_frame.grid_columnconfigure(1, weight=1)
        
        self.right_header = ctk.CTkLabel(
            self.right_top_frame,
            text="Analiz Sonuclari",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.right_header.grid(row=0, column=0, sticky="w", padx=5)
        
        # Arama ve filtre
        self.search_filter_frame = ctk.CTkFrame(self.right_top_frame, fg_color="transparent")
        self.search_filter_frame.grid(row=0, column=2, sticky="e", padx=5)
        
        self.search_label = ctk.CTkLabel(
            self.search_filter_frame,
            text="Ara:",
            font=ctk.CTkFont(size=12)
        )
        self.search_label.grid(row=0, column=0, padx=(0, 5))
        
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.search_filter_frame,
            textvariable=self.search_var,
            width=150,
            placeholder_text="Takim adi...",
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.grid(row=0, column=1, padx=(0, 15))
        self.search_entry.bind('<KeyRelease>', self.on_search)
        
        self.filter_label = ctk.CTkLabel(
            self.search_filter_frame,
            text="Filtre:",
            font=ctk.CTkFont(size=12)
        )
        self.filter_label.grid(row=0, column=2, padx=(0, 5))
        
        self.filter_var = ctk.StringVar(value="Tumu")
        self.filter_dropdown = ctk.CTkOptionMenu(
            self.search_filter_frame,
            values=["Tumu", "Kazanma >=70%", "Kazanma >=60%", "Guven >=60", "4+ Gol >=50%", "0-3 Gol >=70%"],
            variable=self.filter_var,
            command=self.apply_filter,
            width=140,
            font=ctk.CTkFont(size=12)
        )
        self.filter_dropdown.grid(row=0, column=3)
        
        self.last_predictions_df: Optional[pd.DataFrame] = None
        
        # Progress bar
        self.progress_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_frame.grid_remove()
        
        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Analiz ediliyor...",
            font=ctk.CTkFont(size=13)
        )
        self.progress_label.grid(row=0, column=0, pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            mode="indeterminate",
            width=500
        )
        self.progress_bar.grid(row=1, column=0)
        
        # Sonuc text alani
        self.result_text = ctk.CTkTextbox(
            self.right_frame,
            corner_radius=5,
            font=ctk.CTkFont(family="Courier New", size=14),
            wrap="none"
        )
        self.result_text.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        
        self._show_welcome_message()
        
        # ALT PANEL
        self.status_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 10))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Hazir",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.pack(side="left")
    
    def _show_welcome_message(self):
        """Hos geldin mesaji goster."""
        from datetime import date
        today = date.today()
        start_date, end_date = get_week_range()
        welcome = f"""
+====================================================================================================+
|                                   FUTBOL MAC TAHMIN SISTEMI                                        |
+====================================================================================================+

   BUGUN: {today.strftime('%d/%m/%Y')}
   HAFTA: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')} (Sali - Sali arasi, sadece gelecek maclar)
   -------------------------------------------------------------------------------------------------

   KULLANIM:
   -------------------------------------------------------------------------------------------------
   1. Sol panelden analiz etmek istediginiz maclari secin (takim arama kutusunu kullanabilirsiniz)
   2. "Analiz Et" butonuna tiklayin
   3. Sonuclar bu alanda goruntulenecek
   4. 14+ mac secilirse "En Garanti 10-14" butonu aktif olur

   DESTEKLENEN LIGLER:
   -------------------------------------------------------------------------------------------------
   - Ingiltere Premier League, Ispanya La Liga, Italya Serie A
   - Almanya Bundesliga, Fransa Ligue 1
   - Turkiye Super Lig, Portekiz Primeira Liga, Belcika Pro League
   - Suudi Arabistan Pro League
   - UEFA Sampiyonlar Ligi, Avrupa Ligi, Konferans Ligi

   TABLO SUTUNLARI:
   -------------------------------------------------------------------------------------------------
   EV %      : Ev sahibi kazanma olasiligi
   BER %     : Beraberlik olasiligi  
   DEP %     : Deplasman kazanma olasiligi
   0-3 GOL % : 0-3 toplam gol olasiligi (Alt 3.5)
   4+ GOL %  : 4+ toplam gol olasiligi (Ust 3.5)
   GUVEN     : Tahmin guvenilirligi (0-100), form istikrari ve veri kalitesine bagli
   BANKO SK  : (Kazanma %) x (Gol tahmini %) - yuksek = daha guvenli

   ALGORITMA:
   -------------------------------------------------------------------------------------------------
   Poisson Dagilimi + Dixon-Coles Duzeltmesi + Monte Carlo Simulasyonu (5000 tekrar)

+====================================================================================================+
        """
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", welcome)
    
    def _set_status(self, text: str):
        self.status_label.configure(text=text)
    
    def on_left_search(self, event=None):
        """Sol panelde arama yapildiginda."""
        search_text = self.left_search_var.get().strip()
        
        # Hem arama hem de tarih filtresini uygula
        self._apply_left_filters()
    
    def filter_by_date(self, date_key: str):
        """Tarih filtreleme."""
        self.date_filter_var.set(date_key)
        
        # Buton renklerini guncelle
        for key, btn in self.date_buttons.items():
            if key == date_key:
                btn.configure(fg_color="#1E5128")  # Aktif - yesil
            else:
                btn.configure(fg_color="#4A4A4A")  # Pasif - gri
        
        self._apply_left_filters()
    
    def _apply_left_filters(self):
        """Sol paneldeki tum filtreleri uygula (arama + tarih)."""
        search_text = self.left_search_var.get().strip().lower()
        date_filter = self.date_filter_var.get()
        
        total_visible = 0
        
        for section in self.league_sections.values():
            section_visible = 0
            
            for cb in section.match_checkboxes:
                # Arama filtresi
                search_match = cb.matches_search(search_text) if search_text else True
                
                # Tarih filtresi
                if date_filter == "all":
                    date_match = True
                else:
                    match_date = cb.match_data.get('match_date')
                    if match_date is not None:
                        if hasattr(match_date, 'strftime'):
                            match_date_str = match_date.strftime('%Y-%m-%d')[:10]
                        else:
                            match_date_str = str(match_date)[:10]
                        date_match = match_date_str == date_filter
                    else:
                        date_match = False
                
                # Her iki filtre de gecerliyse goster
                if search_match and date_match:
                    cb.show()
                    section_visible += 1
                else:
                    cb.hide()
            
            # Lig basligini gizle/goster
            if section_visible == 0:
                section.header.grid_remove()
                section.separator.grid_remove()
                section.visible = False
            else:
                section.header.grid()
                section.separator.grid()
                section.visible = True
            
            total_visible += section_visible
        
        # Durum mesaji
        filter_info = []
        if search_text:
            filter_info.append(f"Arama: '{search_text}'")
        if date_filter != "all":
            filter_info.append(f"Tarih: {date_filter[8:10]}/{date_filter[5:7]}")
        
        if filter_info:
            self._set_status(f"{' | '.join(filter_info)} - {total_visible} mac")
        else:
            self._set_status(f"{len(self.all_checkboxes)} mac yuklendi")
    
    def on_search(self, event=None):
        """Analiz sonuclarinda arama."""
        if self.last_predictions_df is None or self.last_predictions_df.empty:
            return
        self.apply_filter(self.filter_var.get())
    
    def load_fixtures_async(self):
        """Fiksturu arka planda yukle."""
        self._set_status("Fikstur yukleniyor...")
        self.update_data_btn.configure(state="disabled")
        
        thread = threading.Thread(target=self._load_fixtures_thread)
        thread.daemon = True
        thread.start()
    
    def _load_fixtures_thread(self):
        try:
            self.matches_df = fetch_all_data(
                leagues=SUPPORTED_LEAGUES,
                last_n_matches=10,
                verbose=True
            )
            self.after(0, self._populate_matches)
        except Exception as e:
            self.after(0, lambda: self._show_error(f"Fikstur yuklenirken hata: {e}"))
        finally:
            self.after(0, lambda: self.update_data_btn.configure(state="normal"))
    
    def _populate_matches(self):
        """Mac listesini doldur."""
        for widget in self.matches_scroll.winfo_children():
            widget.destroy()
        
        self.league_sections.clear()
        self.all_checkboxes.clear()
        
        if self.matches_df is None or self.matches_df.empty:
            no_match_label = ctk.CTkLabel(
                self.matches_scroll,
                text="Bu hafta mac bulunamadi",
                font=ctk.CTkFont(size=14)
            )
            no_match_label.grid(row=0, column=0, pady=50)
            self._set_status("Mac bulunamadi")
            return
        
        df = self.matches_df.copy()
        if 'match_date' in df.columns:
            df['match_date'] = pd.to_datetime(df['match_date'])
            df = df.sort_values(['league_display', 'match_date'])
        
        current_row = 0
        for league_display in df['league_display'].unique():
            league_matches = df[df['league_display'] == league_display]
            league_code = league_matches.iloc[0]['league']
            
            section = LeagueSection(
                self.matches_scroll,
                league_code,
                league_display,
                league_matches,
                current_row
            )
            
            self.league_sections[league_code] = section
            self.all_checkboxes.extend(section.match_checkboxes)
            current_row = section.end_row
        
        total = len(self.all_checkboxes)
        self._set_status(f"{total} mac yuklendi ({len(self.league_sections)} lig)")
    
    def toggle_select_all(self):
        """Tumunu sec/kaldir."""
        visible_checkboxes = [cb for cb in self.all_checkboxes if cb.visible]
        any_selected = any(cb.is_selected() for cb in visible_checkboxes)
        
        for cb in visible_checkboxes:
            cb.set_selected(not any_selected)
        
        self._update_top10_button()
        
        if any_selected:
            self.select_all_btn.configure(text="Tumunu Sec")
        else:
            self.select_all_btn.configure(text="Secimi Kaldir")
    
    def _update_top10_button(self):
        """En Garanti 10-14 butonunun durumunu guncelle."""
        selected_count = sum(1 for cb in self.all_checkboxes if cb.is_selected())
        
        if selected_count > 14:
            self.top10_btn.configure(state="normal")
        else:
            self.top10_btn.configure(state="disabled")
    
    def select_top_guaranteed(self):
        """Analiz sonuclarindan en garanti 10-14 maci sec."""
        if self.last_predictions_df is None or self.last_predictions_df.empty:
            messagebox.showinfo("Bilgi", "Once analiz yapmaniz gerekiyor!")
            return
        
        # En yuksek banko skoruna gore sirala
        df = self.last_predictions_df.copy()
        df = df.sort_values('banko_score', ascending=False)
        
        # Ilk 12 maci al (10-14 arasi)
        top_matches = df.head(12)
        
        # Sadece bu maclari goster
        result_text = self._format_results_clean(top_matches)
        self._show_results(result_text)
        
        self._set_status(f"En garanti 12 mac gosteriliyor (Banko skoruna gore)")
    
    def update_data(self):
        clear_cache()
        self._set_status("Onbellek temizlendi, yeni veriler cekiliyor...")
        self.load_fixtures_async()
    
    def clear_results(self):
        self.last_predictions_df = None
        self.search_var.set("")
        self._show_welcome_message()
        self._set_status("Tablo temizlendi")
    
    def apply_filter(self, filter_value: str):
        if self.last_predictions_df is None or self.last_predictions_df.empty:
            return
        
        df = self.last_predictions_df.copy()
        
        # Arama filtresi
        search_text = self.search_var.get().strip().lower()
        if search_text:
            df = df[
                df['home_team'].str.lower().str.contains(search_text, na=False) |
                df['away_team'].str.lower().str.contains(search_text, na=False)
            ]
        
        # Diger filtreler
        if filter_value == "Kazanma >=70%":
            df = df[df['win_prob'] >= 70]
        elif filter_value == "Kazanma >=60%":
            df = df[df['win_prob'] >= 60]
        elif filter_value == "Guven >=60":
            df = df[df['confidence'] >= 60]
        elif filter_value == "4+ Gol >=50%":
            df = df[df['over_3.5_%'] >= 50]
        elif filter_value == "0-3 Gol >=70%":
            df = df[df['under_3.5_%'] >= 70]
        
        if df.empty:
            self.result_text.delete("1.0", "end")
            msg = f"\n\nArama/filtre kriterine uyan mac bulunamadi.\n"
            if search_text:
                msg += f"\nArama: '{search_text}'"
            msg += f"\nFiltre: {filter_value}"
            self.result_text.insert("1.0", msg)
            self._set_status(f"0 mac bulundu")
            return
        
        result_text = self._format_results_clean(df)
        self._show_results(result_text)
        self._set_status(f"{len(df)} mac gosteriliyor")
    
    def run_analysis(self):
        selected = [cb.get_data() for cb in self.all_checkboxes if cb.is_selected()]
        
        if not selected:
            messagebox.showwarning("Uyari", "Lutfen en az bir mac secin!")
            return
        
        self._set_status(f"{len(selected)} mac analiz ediliyor...")
        self.analyze_btn.configure(state="disabled")
        self.select_all_btn.configure(state="disabled")
        self.update_data_btn.configure(state="disabled")
        self.top10_btn.configure(state="disabled")
        
        self._show_progress(f"{len(selected)} mac analiz ediliyor...")
        
        thread = threading.Thread(target=lambda: self._analyze_thread(selected))
        thread.daemon = True
        thread.start()
    
    def _show_progress(self, text: str):
        self.progress_label.configure(text=text)
        self.progress_frame.grid()
        self.progress_bar.start()
    
    def _hide_progress(self):
        self.progress_bar.stop()
        self.progress_frame.grid_remove()
    
    def _analyze_thread(self, selected_matches: List[dict]):
        try:
            selected_df = pd.DataFrame(selected_matches)
            
            predictor = MatchPredictor()
            predictions = predictor.predict_all_matches(selected_df)
            predictions_df = predictions_to_dataframe(predictions)
            
            predictions_df['league'] = selected_df['league'].values
            if 'league_display' in selected_df.columns:
                predictions_df['league_display'] = selected_df['league_display'].values
            
            banko_scores = []
            favorites = []
            win_probs = []
            
            for _, row in predictions_df.iterrows():
                score, _ = calculate_banko_score(row)
                banko_scores.append(score)
                
                if row['home_win_%'] > row['away_win_%'] and row['home_win_%'] > row['draw_%']:
                    favorites.append(row['home_team'])
                    win_probs.append(row['home_win_%'])
                elif row['away_win_%'] > row['home_win_%'] and row['away_win_%'] > row['draw_%']:
                    favorites.append(row['away_team'])
                    win_probs.append(row['away_win_%'])
                else:
                    favorites.append('Beraberlik')
                    win_probs.append(row['draw_%'])
            
            predictions_df['banko_score'] = banko_scores
            predictions_df['favorite'] = favorites
            predictions_df['win_prob'] = win_probs
            
            self.last_predictions_df = predictions_df.copy()
            
            self.after(0, lambda: self.filter_var.set("Tumu"))
            self.after(0, lambda: self.search_var.set(""))
            
            # En Garanti 10-14 butonunu guncelle
            if len(predictions_df) > 14:
                self.after(0, lambda: self.top10_btn.configure(state="normal"))
            
            result_text = self._format_results_clean(predictions_df)
            self.after(0, lambda: self._show_results(result_text))
            
        except Exception as e:
            import traceback
            self.after(0, lambda: self._show_error(f"Analiz hatasi: {e}\n{traceback.format_exc()}"))
        
        finally:
            self.after(0, self._hide_progress)
            self.after(0, lambda: self.analyze_btn.configure(state="normal"))
            self.after(0, lambda: self.select_all_btn.configure(state="normal"))
            self.after(0, lambda: self.update_data_btn.configure(state="normal"))
            self.after(0, lambda: self._set_status("Analiz tamamlandi"))
    
    def _format_results_clean(self, predictions_df: pd.DataFrame) -> str:
        W = 120
        lines = []
        
        predictions_df = predictions_df.copy()
        
        if 'banko_score' not in predictions_df.columns:
            banko_scores = []
            favorites = []
            win_probs = []
            
            for _, row in predictions_df.iterrows():
                score, _ = calculate_banko_score(row)
                banko_scores.append(score)
                
                if row['home_win_%'] > row['away_win_%'] and row['home_win_%'] > row['draw_%']:
                    favorites.append(row['home_team'])
                    win_probs.append(row['home_win_%'])
                elif row['away_win_%'] > row['home_win_%'] and row['away_win_%'] > row['draw_%']:
                    favorites.append(row['away_team'])
                    win_probs.append(row['away_win_%'])
                else:
                    favorites.append('Beraberlik')
                    win_probs.append(row['draw_%'])
            
            predictions_df['banko_score'] = banko_scores
            predictions_df['favorite'] = favorites
            predictions_df['win_prob'] = win_probs
        
        banko_idx = predictions_df['banko_score'].idxmax()
        banko = predictions_df.loc[banko_idx]
        
        # BASLIK
        lines.append("")
        lines.append("+" + "=" * W + "+")
        lines.append("|" + "HIBRIT ANALIZ SONUCLARI".center(W) + "|")
        lines.append("|" + "(Poisson + Dixon-Coles + Monte Carlo)".center(W) + "|")
        lines.append("+" + "=" * W + "+")
        
        # HAFTANIN BANKOSU
        lines.append("|" + " " * W + "|")
        lines.append("|" + "*** HAFTANIN BANKOSU ***".center(W) + "|")
        lines.append("|" + " " * W + "|")
        
        match_str = f"{banko['home_team']}  vs  {banko['away_team']}"
        lines.append("|" + match_str.center(W) + "|")
        lines.append("|" + " " * W + "|")
        
        fav_str = f"FAVORI: {banko['favorite']}  ({banko['win_prob']:.1f}%)"
        lines.append("|" + fav_str.center(W) + "|")
        
        odds_str = f"EV: {banko['home_win_%']:.1f}%  |  BERABERLIK: {banko['draw_%']:.1f}%  |  DEPLASMAN: {banko['away_win_%']:.1f}%"
        lines.append("|" + odds_str.center(W) + "|")
        
        if banko['under_3.5_%'] > banko['over_3.5_%']:
            goal_str = f"GOL TAHMINI: 0-3 Gol ({banko['under_3.5_%']:.1f}%)"
        else:
            goal_str = f"GOL TAHMINI: 4+ Gol ({banko['over_3.5_%']:.1f}%)"
        lines.append("|" + goal_str.center(W) + "|")
        
        conf_str = f"GUVEN SKORU: {banko['confidence']:.0f}/100  |  BANKO SKORU: {banko['banko_score']:.1f}"
        lines.append("|" + conf_str.center(W) + "|")
        
        lines.append("|" + " " * W + "|")
        lines.append("+" + "=" * W + "+")
        
        # TABLO BASLIGI
        header = "| {:^28} | {:^8} | {:^8} | {:^8} | {:^9} | {:^9} | {:^7} | {:^9} |"
        lines.append(header.format("MAC", "EV %", "BER %", "DEP %", "0-3 GOL%", "4+ GOL%", "GUVEN", "BANKO SK"))
        lines.append("+" + "-" * W + "+")
        
        row_format = "| {:^28} | {:^8.1f} | {:^8.1f} | {:^8.1f} | {:^9.1f} | {:^9.1f} | {:^7.0f} | {:^9.1f} |"
        
        # YUKSEK GUVENLI MACLAR
        high_conf_indices = []
        for idx, row in predictions_df.iterrows():
            if idx == banko_idx:
                continue
            max_win = max(row['home_win_%'], row['away_win_%'])
            max_goal = max(row['under_3.5_%'], row['over_3.5_%'])
            if max_win >= 70 and max_goal >= 65:
                high_conf_indices.append(idx)
        
        if high_conf_indices:
            lines.append("|" + "YUKSEK GUVENLI MACLAR".center(W) + "|")
            lines.append("+" + "-" * W + "+")
            
            for idx in high_conf_indices:
                row = predictions_df.loc[idx]
                match_str = f"{row['home_team'][:12]} vs {row['away_team'][:12]}"
                lines.append(row_format.format(
                    match_str,
                    row['home_win_%'],
                    row['draw_%'],
                    row['away_win_%'],
                    row['under_3.5_%'],
                    row['over_3.5_%'],
                    row['confidence'],
                    row['banko_score']
                ))
            
            lines.append("+" + "-" * W + "+")
        
        # DIGER MACLAR
        other_indices = [i for i in predictions_df.index 
                        if i != banko_idx and i not in high_conf_indices]
        
        if other_indices:
            lines.append("|" + "DIGER MACLAR".center(W) + "|")
            lines.append("+" + "-" * W + "+")
            
            other_df = predictions_df.loc[other_indices].sort_values('banko_score', ascending=False)
            
            for _, row in other_df.iterrows():
                match_str = f"{row['home_team'][:12]} vs {row['away_team'][:12]}"
                lines.append(row_format.format(
                    match_str,
                    row['home_win_%'],
                    row['draw_%'],
                    row['away_win_%'],
                    row['under_3.5_%'],
                    row['over_3.5_%'],
                    row['confidence'],
                    row['banko_score']
                ))
        
        # ALT BILGI - TERIMLER VE ACIKLAMALAR
        lines.append("+" + "=" * W + "+")
        lines.append("|" + " " * W + "|")
        lines.append("|" + "TABLO ACIKLAMALARI".center(W) + "|")
        lines.append("|" + "-" * (W-2).center(W) + "|")
        lines.append("|" + " " * W + "|")
        lines.append("|  EV %       : Ev sahibi takimin kazanma olasiligi                                                   |")
        lines.append("|  BER %      : Beraberlik olasiligi                                                                  |")
        lines.append("|  DEP %      : Deplasman takiminin kazanma olasiligi                                                 |")
        lines.append("|  0-3 GOL %  : Macta toplam 0, 1, 2 veya 3 gol atilma olasiligi (Alt 3.5)                            |")
        lines.append("|  4+ GOL %   : Macta 4 veya daha fazla gol atilma olasiligi (Ust 3.5)                                |")
        lines.append("|" + " " * W + "|")
        lines.append("|  GUVEN      : Tahminin guvenilirlik skoru (0-100)                                                   |")
        lines.append("|               - Takimlarin form istikrari                                                           |")
        lines.append("|               - Olasilik farki (acik favori = yuksek guven)                                         |")
        lines.append("|               - Veri kalitesi ve tutarliligi                                                        |")
        lines.append("|" + " " * W + "|")
        lines.append("|  BANKO SK   : Banko Skoru = (En yuksek kazanma %) x (En yuksek gol araligi %)                       |")
        lines.append("|               Ornek: %70 kazanma x %65 gol tahmini = 45.5 banko skoru                               |")
        lines.append("|               Yuksek skor = Daha guvenli bahis                                                      |")
        lines.append("|" + " " * W + "|")
        lines.append("|" + "-" * (W-2).center(W) + "|")
        lines.append("|" + "HESAPLAMA YONTEMI".center(W) + "|")
        lines.append("|" + "-" * (W-2).center(W) + "|")
        lines.append("|" + " " * W + "|")
        lines.append("|  1. POISSON DAGILIMI    : Takimlarin son 5-10 mactaki gol ortalamalarindan beklenen gol hesabi      |")
        lines.append("|  2. DIXON-COLES         : Dusuk skorlu maclarda (0-0, 1-0, 1-1) korelasyon duzeltmesi               |")
        lines.append("|  3. MONTE CARLO         : 5000 mac simulasyonu ile belirsizlik analizi                              |")
        lines.append("|  4. GUC PUANI           : Hucum ve savunma rating'i (form + xG verisi)                              |")
        lines.append("|" + " " * W + "|")
        lines.append("|  Hibrit Sonuc: Poisson (%60) + Monte Carlo (%40) birlesimi                                          |")
        lines.append("|" + " " * W + "|")
        lines.append("+" + "=" * W + "+")
        
        return "\n".join(lines)
    
    def _show_results(self, text: str):
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
    
    def _show_error(self, message: str):
        self._set_status(f"Hata: {message}")
        messagebox.showerror("Hata", message)


def main():
    try:
        app = FutbolTahminApp()
        app.mainloop()
    except Exception as e:
        print(f"Uygulama hatasi: {e}")
        import traceback
        traceback.print_exc()
        # Hata durumunda sessizce kapat, tekrar baslatma
        import sys
        sys.exit(0)


if __name__ == "__main__":
    # macOS'ta tekrar baslatmayi engelle
    import sys
    import os
    
    # Frozen (paketlenmis) uygulama kontrolu
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmis
        os.environ['PYINSTALLER_FROZEN'] = '1'
    
    main()
