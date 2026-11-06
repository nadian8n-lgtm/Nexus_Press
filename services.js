function updateMoroccoWeatherAndPrayer() {
  const cityInput = document.getElementById('service-city');
  const countryInput = document.getElementById('service-country');
  const weather = document.getElementById('weather-status');
  const prayer = document.getElementById('prayer-status');
  if (!cityInput || !countryInput || !weather || !prayer) return;

  const lookup = async () => {
    const city = cityInput.value.trim();
    const country = countryInput.value.trim();
    if (!city || !country) return;
    weather.textContent = 'جارٍ تحميل الطقس…';
    prayer.textContent = 'جارٍ تحميل مواقيت الصلاة…';

    try {
      const search = new URL('https://geocoding-api.open-meteo.com/v1/search');
      search.search = new URLSearchParams({ name: city, count: '1', language: 'ar', format: 'json' });
      const geoResponse = await fetch(search);
      if (!geoResponse.ok) throw new Error('تعذر تحديد المدينة');
      const geo = await geoResponse.json();
      const place = (geo.results || []).find(item => !country || item.country_code === country || item.country === country);
      if (!place) throw new Error('لم يتم العثور على المدينة');

      const weatherUrl = new URL('https://api.open-meteo.com/v1/forecast');
      weatherUrl.search = new URLSearchParams({
        latitude: String(place.latitude), longitude: String(place.longitude),
        current: 'temperature_2m,relative_humidity_2m,weather_code',
        timezone: 'auto'
      });
      const weatherResponse = await fetch(weatherUrl);
      if (!weatherResponse.ok) throw new Error('تعذر تحميل الطقس');
      const weatherData = await weatherResponse.json();
      weather.textContent = `${place.name} (${place.country}): ${weatherData.current.temperature_2m}°م · الرطوبة ${weatherData.current.relative_humidity_2m}%`;

      const prayerUrl = new URL('https://api.aladhan.com/v1/timingsByCity');
      prayerUrl.search = new URLSearchParams({ city: place.name, country: place.country, method: '21' });
      const prayerResponse = await fetch(prayerUrl);
      if (!prayerResponse.ok) throw new Error('تعذر تحميل المواقيت');
      const prayerData = await prayerResponse.json();
      if (prayerData.code !== 200 || !prayerData.data?.timings) throw new Error('مواقيت الصلاة غير متاحة لهذه المدينة');
      const times = prayerData.data.timings;
      prayer.textContent = `${place.name}: الفجر ${times.Fajr} · الظهر ${times.Dhuhr} · العصر ${times.Asr} · المغرب ${times.Maghrib} · العشاء ${times.Isha}`;
    } catch (error) {
      weather.textContent = `الطقس: ${error.message}`;
      prayer.textContent = `مواقيت الصلاة: ${error.message}`;
    }
  };

  document.getElementById('service-city-submit')?.addEventListener('click', lookup);
  cityInput.addEventListener('keydown', event => { if (event.key === 'Enter') lookup(); });
  lookup();
}

document.addEventListener('DOMContentLoaded', updateMoroccoWeatherAndPrayer);
