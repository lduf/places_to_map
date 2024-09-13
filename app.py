import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import io
import base64

# Importations pour Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

st.title("Visualisation personnalisée sur la Carte de France")

# 1. Chargement du fichier CSV
uploaded_file = st.file_uploader("Choisissez un fichier CSV", type="csv")

if uploaded_file is not None:
    # Lecture du fichier CSV
    df = pd.read_csv(uploaded_file, sep=';')

    # Vérification des colonnes nécessaires
    required_columns = {'nom', 'adresse', 'catégorie'}
    if not required_columns.issubset(df.columns):
        st.error(f"Le fichier CSV doit contenir les colonnes : {', '.join(required_columns)}")
    else:
        # 2. Géocodage des adresses
        geolocator = Nominatim(user_agent="my_geocoder")

        @st.cache_data
        def geocode_address(address):
            try:
                location = geolocator.geocode(f"{address}, France")
                return location.latitude, location.longitude
            except:
                return None, None

        if 'latitude' not in df.columns or 'longitude' not in df.columns:
            st.info("Géocodage des adresses, cela peut prendre quelques minutes...")
            df[['latitude', 'longitude']] = df['adresse'].apply(lambda x: pd.Series(geocode_address(x)))

        # Suppression des adresses non géocodées
        df = df.dropna(subset=['latitude', 'longitude'])

        # **Sélection des catégories à afficher**
        all_categories = df['catégorie'].unique()
        selected_categories = st.multiselect(
            "Sélectionnez les catégories à afficher sur la carte",
            options=all_categories,
            default=all_categories
        )

        # **Menu d'options pour paramétrer l'affichage**
        st.sidebar.header("Options de la carte")

        # **Ajouter l'option de sélection du fond de carte**
        map_tiles = {
            'OpenStreetMap': {'tiles': 'OpenStreetMap', 'attr': ''},
            'CartoDB positron': {'tiles': 'CartoDB positron', 'attr': ''},
            'France départements': {
                # Remplacez par l'URL où vos tuiles sont hébergées sur GitHub Pages
                'tiles': 'https://lduf.github.io/places_to_map/tiles/{z}/{x}/{y}.png',
                'attr': 'Votre attribution ici'
            }
        }

        selected_tile = st.sidebar.selectbox(
            "Choisissez le fond de carte",
            options=list(map_tiles.keys()),
            index=0  # Par défaut, le premier de la liste
        )

        force_points = st.sidebar.checkbox("Forcer la vue des points (désactiver le regroupement)", value=False)
        show_labels = st.sidebar.checkbox("Afficher le nom du lieu sous le point (lors de l'export)", value=False)

        # Filtrer le DataFrame en fonction des catégories sélectionnées
        filtered_df = df[df['catégorie'].isin(selected_categories)]

        # 3. Création de la carte
        tile_settings = map_tiles[selected_tile]

        # Initialiser la carte sans fond de carte
        m = folium.Map(
            location=[46.5, 2.5],
            zoom_start=6,
            tiles=None,  # Pas de fond de carte initial
            control_scale=False,
            zoom_control=True,
            prefer_canvas=True,
        )

        # Ajouter le fond de carte en tant que TileLayer séparé
        if tile_settings['tiles'] is not None:
            tile_layer = folium.TileLayer(
                tiles=tile_settings['tiles'],
                attr=tile_settings['attr'],
                name="Fond de carte",
                control=False
            )
            tile_layer.add_to(m)

        # **Ajustement de la vue pour inclure tous les points**
        if not filtered_df.empty:
            sw = filtered_df[['latitude', 'longitude']].min().values.tolist()
            ne = filtered_df[['latitude', 'longitude']].max().values.tolist()
            m.fit_bounds([sw, ne])

        # Création d'un groupe de marqueurs en fonction de l'option
        if force_points:
            marker_group = folium.FeatureGroup(name='Points').add_to(m)
        else:
            marker_group = MarkerCluster().add_to(m)

        # Couleurs pour les catégories
        categories = filtered_df['catégorie'].unique()
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred',
                  'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white',
                  'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
        color_map = dict(zip(categories, colors))

        # Ajout des points sur la carte
        for idx, row in filtered_df.iterrows():
            if show_labels:
                # Création d'un DivIcon avec le nom du lieu
                icon = folium.DivIcon(
                    html=f"""
                        <div style="text-align:center;">
                            <i class="fa fa-circle fa-2x" style="color:{color_map.get(row['catégorie'], 'blue')};"></i>
                            <div style="font-size: 10px; color: {color_map.get(row['catégorie'], 'blue')};">{row['nom']}</div>
                        </div>
                    """
                )
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    icon=icon
                ).add_to(marker_group)
            else:
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=5,
                    color=color_map.get(row['catégorie'], 'blue'),
                    fill=True,
                    fill_color=color_map.get(row['catégorie'], 'blue'),
                    fill_opacity=1,
                ).add_to(marker_group)

        # **Ajouter une légende personnalisée**
        def generate_legend_html(color_map):
            html = """
            <div style="
                position: fixed;
                bottom: 50px;
                left: 50px;
                width: 150px;
                height: auto;
                z-index:9999;
                font-size:14px;
                background-color: white;
                opacity: 0.8;
                padding: 10px;
                ">
                <h4>Légende</h4>
                <ul style="list-style: none; padding: 0; margin: 0;">"""
            for category, color in color_map.items():
                html += f"""
                    <li style="margin-bottom: 5px;">
                        <span style="display: inline-block; width: 12px; height: 12px; background-color: {color}; margin-right: 5px; border-radius: 50%;"></span>
                        {category}
                    </li>
                """
            html += """
                </ul>
            </div>
            """
            return html

        legend_html = generate_legend_html(color_map)
        m.get_root().html.add_child(folium.Element(legend_html))

        # **Option pour rendre le fond transparent lors de l'export en PNG**
        if selected_tile == 'France départements':
            # Garder le fond de carte personnalisé lors de l'export
            transparent_background = False
        else:
            # Rendre le fond transparent lors de l'export
            transparent_background = True

        # 4. Affichage de la carte dans Streamlit
        st_data = st_folium(m, width=900, height=700)

        # **Boutons de téléchargement**
        col1, col2 = st.columns(2)

        with col1:
            # Téléchargement de la carte en PNG
            if st.button("Télécharger la carte en PNG"):
                st.info("Génération de l'image PNG de la carte...")

                # **Ajustement de la vue pour inclure tous les points avant l'export**
                if not filtered_df.empty:
                    sw = filtered_df[['latitude', 'longitude']].min().values.tolist()
                    ne = filtered_df[['latitude', 'longitude']].max().values.tolist()
                    m.fit_bounds([sw, ne])

                # **Désactiver le fond de carte lors de l'export pour un fond transparent**
                if transparent_background and 'tile_layer' in locals():
                    m.remove_child(tile_layer)

                # Configuration de Selenium
                options = Options()
                options.add_argument("--headless")
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')

                # Initialisation du driver
                driver = webdriver.Chrome(options=options)  # Assurez-vous que ChromeDriver est installé

                # Génération de l'image PNG
                png_data = m._to_png(driver=driver)
                driver.quit()

                # Rétablir le fond de carte original
                if transparent_background and 'tile_layer' in locals():
                    m.add_child(tile_layer)

                # Téléchargement du PNG
                st.download_button(
                    label="Cliquez ici pour télécharger l'image PNG",
                    data=png_data,
                    file_name='carte.png',
                    mime='image/png'
                )

        with col2:
            # Téléchargement de la carte en HTML
            folium_html = m.get_root().render()
            b64 = base64.b64encode(folium_html.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="carte.html">Cliquez ici pour télécharger la carte en HTML</a>'
            st.markdown(href, unsafe_allow_html=True)