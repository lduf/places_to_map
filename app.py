import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, Fullscreen
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import io
import base64

# Importations pour Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Importation pour ajouter du HTML personnalisé
from folium import Element

st.title("Visualisation personnalisée sur la Carte de France")

# 1. Saisie du titre par l'utilisateur
map_title = st.text_input("Entrez le titre de la carte :", "Ma Carte")

# 2. Chargement du fichier CSV
uploaded_file = st.file_uploader("Choisissez un fichier CSV", type="csv")

if uploaded_file is not None:
    # Lecture du fichier CSV avec le bon séparateur et l'encodage
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8-sig')
        # Afficher les colonnes pour débogage
        st.write("Colonnes du DataFrame :", df.columns.tolist())
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier CSV : {e}")
    else:
        # Vérification des colonnes nécessaires
        required_columns = {'nom', 'adresse', 'catégorie'}
        if not required_columns.issubset(df.columns):
            st.error(f"Le fichier CSV doit contenir les colonnes : {', '.join(required_columns)}")
        else:
            # 3. Géocodage des adresses
            geolocator = Nominatim(user_agent="my_geocoder")

            @st.cache_data
            def geocode_address(address):
                try:
                    location = geolocator.geocode(f"{address}, France")
                    # st.write(f"Géocodage réussi pour {address} : {location}")
                    return location.latitude, location.longitude
                except Exception as e:
                    st.write(f"Erreur de géocodage pour {address} : {e}")
                    return None, None

            if 'latitude' not in df.columns or 'longitude' not in df.columns:
                st.info("Géocodage des adresses, cela peut prendre quelques minutes...")
                df[['latitude', 'longitude']] = df['adresse'].apply(lambda x: pd.Series(geocode_address(x)))
                
            # Permettre le téléchargement du fichier avec la latitude / longitude
            st.download_button(
                        label="Cliquez ici pour télécharger le csv avec la latitude / longitude",
                        data=df,
                        file_name='lat_long.csv',
                        mime='data/csv'
                    )

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
            enable_fullscreen = st.sidebar.checkbox("Activer le mode plein écran", value=True)

            # Option pour la taille des noms
            font_size_option = st.sidebar.selectbox(
                "Taille des noms affichés sur la carte",
                options=["Petit", "Moyen", "Grand", "Très grand"],
                index=1  # Par défaut, "Moyen"
            )

            # Mapper les options à des tailles en pixels
            font_size_map = {
                "Petit": 15,
                "Moyen": 25,
                "Grand": 35,
                "Très grand": 50
            }

            font_size = font_size_map[font_size_option]

            # Filtrer le DataFrame en fonction des catégories sélectionnées
            filtered_df = df[df['catégorie'].isin(selected_categories)]

            # 4. Création de la carte
            tile_settings = map_tiles[selected_tile]

            tile_layer = None  # Initialiser tile_layer à None

            if selected_tile == 'France départements':
                # Pour le fond de carte personnalisé, ajouter en tant que TileLayer
                m = folium.Map(
                    location=[46.5, 2.5],
                    zoom_start=6,
                    tiles=None,  # Pas de fond de carte initial
                    control_scale=False,
                    zoom_control=True,
                    prefer_canvas=True,
                )
                tile_layer = folium.TileLayer(
                    tiles=tile_settings['tiles'],
                    attr=tile_settings['attr'],
                    name="Fond de carte",
                    control=False
                )
                tile_layer.add_to(m)
            else:
                # Pour les fonds de carte par défaut
                m = folium.Map(
                    location=[46.5, 2.5],
                    zoom_start=6,
                    tiles=tile_settings['tiles'],
                    attr=tile_settings['attr'],
                    control_scale=False,
                    zoom_control=True,
                    prefer_canvas=True,
                )

            # Activer le mode plein écran si sélectionné
            if enable_fullscreen:
                Fullscreen().add_to(m)

            # **Ajustement de la vue pour inclure tous les points (uniquement pour l'affichage)**
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
                color = color_map.get(row['catégorie'], 'blue')
                if show_labels:
                    # Création d'un DivIcon avec le nom du lieu
                    icon = folium.DivIcon(
                        html=f"""
                            <div style="text-align:center; white-space: nowrap;">
                                <i class="fa fa-circle fa-2x" style="color:{color};"></i>
                                <div style="font-size: {font_size}px; color: {color}; font-weight: bold;">{row['nom']}</div>
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
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=1,
                    ).add_to(marker_group)

            # **Ajouter une légende personnalisée**
            def generate_legend_html(color_map):
                html = """
                <div style="
                    position: fixed;
                    bottom: 50px;
                    left: 50px;
                    width: 300px;
                    height: auto;
                    z-index:9999;
                    font-size:30px;
                    background-color: white;
                    opacity: 0.8;
                    padding: 10px;
                    ">
                    <h2>Légende</h2>
                    <ul style="list-style: none; padding: 0; margin: 0;">"""
                for category, color in color_map.items():
                    html += f"""
                        <li style="margin-bottom: 5px;">
                            <span style="display: inline-block; width: 25px; height: 25px; background-color: {color}; margin-right: 5px; border-radius: 50%;"></span>
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
            # Désactiver le fond transparent pour tous les fonds de carte
            transparent_background = True

            # 5. Affichage de la carte dans Streamlit
            st_data = st_folium(m, width=900, height=700)

            # **Boutons de téléchargement**
            col1, col2 = st.columns(2)

            with col1:
                # Téléchargement de la carte en PNG
                if st.button("Télécharger la carte en PNG"):
                    st.info("Génération de l'image PNG de la carte...")

                    # **Création d'une copie de la carte pour l'export**
                    export_map = folium.Map(
                        location=[46.5, 2.5],
                        zoom_start=8,
                        tiles=None,
                        control_scale=False,
                        zoom_control=False,
                        prefer_canvas=True,
                        width=3000,
                        height=3000  # Ajustez la hauteur si nécessaire
                    )

                    # Ajouter le fond de carte
                    if selected_tile == 'France départements' and tile_layer is not None:
                        tile_layer.add_to(export_map)
                    else:
                        # Pour les fonds de carte par défaut
                        folium.TileLayer(
                            tiles=tile_settings['tiles'],
                            attr=tile_settings['attr'],
                            name="Fond de carte",
                            control=False
                        ).add_to(export_map)

                    # Ajouter les marqueurs
                    if force_points:
                        marker_group_export = folium.FeatureGroup(name='Points').add_to(export_map)
                    else:
                        marker_group_export = MarkerCluster().add_to(export_map)

                    for idx, row in filtered_df.iterrows():
                        color = color_map.get(row['catégorie'], 'blue')
                        if show_labels:
                            # Création d'un DivIcon avec le nom du lieu
                            icon = folium.DivIcon(
                                html=f"""
                                    <div style="text-align:center; white-space: nowrap;">
                                        <i class="fa fa-circle fa-2x" style="color:{color};"></i>
                                        <div style="font-size: {font_size}px; color: {color}; font-weight: bold;">{row['nom']}</div>
                                    </div>
                                """
                            )
                            folium.Marker(
                                location=[row['latitude'], row['longitude']],
                                icon=icon
                            ).add_to(marker_group_export)
                        else:
                            folium.CircleMarker(
                                location=[row['latitude'], row['longitude']],
                                radius=5,
                                color=color,
                                fill=True,
                                fill_color=color,
                                fill_opacity=1,
                            ).add_to(marker_group_export)

                    # Ajouter la légende
                    export_map.get_root().html.add_child(folium.Element(legend_html))

                    # Ajouter le titre sur la carte exportée
                    title_html = f'''
                        <div style="position: fixed; top: 10px; width: 100%; text-align: center; z-index: 9999;">
                            <h2 style="font-size:50px; background-color: white; display: inline-block; padding: 5px;">{map_title}</h2>
                        </div>
                        '''
                    export_map.get_root().html.add_child(folium.Element(title_html))

                    # Configuration des options pour Chrome
                    options = Options()
                    options.add_argument('--headless')  # Exécution en mode headless
                    options.add_argument('--no-sandbox')  # Nécessaire pour certains environnements de serveurs
                    options.add_argument('--disable-dev-shm-usage')  # Pour éviter des problèmes de mémoire partagée sur certains serveurs
                    options.add_argument('--disable-gpu')  # Désactiver l'accélération matérielle
                    
                    # Initialisation du driver
                    driver = webdriver.Chrome(options=options)

                    # Définir la taille de la fenêtre du navigateur
                    driver.set_window_size(3000, 3000)  # Ajustez les valeurs selon vos besoins

                    # Génération de l'image PNG
                    png_data = export_map._to_png(driver=driver)
                    driver.quit()

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