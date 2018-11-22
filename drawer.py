from plotly.offline import iplot
import plotly.graph_objs as go
import plotly.io as pio
import os
import numpy as np


def draw_candlestick_st(df, st):
    layout = dict(
        xaxis=dict(
            rangeslider=dict(
                visible=False
            )
        )
    )

    fig = go.Figure(layout=layout)

    fig.add_candlestick(x=df.index, open=df.open, high=df.high, low=df.low, close=df.close,
                        increasing=dict(line=dict(color='#FF534D')),
                        decreasing=dict(line=dict(color='#77C34F')), name='Stick')

    fix = st[st.values != 0]
    fig.add_scatter(x=fix.index, y=fix, marker={'color': '#706fd3'}, name='Scatter')

    # iplot(fig)
    file_name = 'sta.png'
    try:
        pio.write_image(fig, file_name, scale=2)
    except Exception as e:
        print(e)
        return None

    return file_name


def main():
    pass


if __name__ == '__main__':
    main()
